"""
Core email sending logic.

Handles recipient resolution, email construction, batching,
retry logic, and template-based sending.
"""

import logging
import re
import time
from email.mime.image import MIMEImage
from html import unescape

from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import transaction
from django.template import Template, Context
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from djgentelella.async_notification.models import (
    EmailNotification, EmailTemplate, AttachedFile,
    NewsLetterTask, suppressed_emails, consented_emails,
)
from djgentelella.async_notification.preview import wrap_in_base_template
from djgentelella.async_notification.resolvers import RecipientResolverRegistry
from djgentelella.async_notification.unsubscribe import unsubscribe_headers
from djgentelella.async_notification.settings import (
    ASYNC_NOTIFICATION_MAX_PER_MAIL,
    ASYNC_NOTIFICATION_MAX_RETRIES,
    ASYNC_NOTIFICATION_RETRY_DELAY,
    ASYNC_NOTIFICATION_RATE_LIMIT,
    ASYNC_NOTIFICATION_REQUIRE_OPTIN,
    ASYNC_NOTIFICATION_MAILING_ADDRESS,
    ASYNC_NOTIFICATION_LIST_ID,
    ASYNC_BCC,
    ASYNC_CC,
    ASYNC_NEWSLETTER_SEVER_CONFIGS,
)

logger = logging.getLogger(__name__)

# Matches <img src=".../preview-file/<pk>"> produced by the WYSIWYG uploader.
INLINE_IMG_RE = re.compile(r'src="([^"]*/preview[-_]file/(\d+)/?)"')


def as_email_list(value):
    """Normalize a recipients value to a clean list of tokens.

    Accepts either a JSON list (the new storage format) or a
    comma-separated string (legacy/settings values), and returns a list
    of stripped, non-empty tokens.
    """
    if not value:
        return []
    if isinstance(value, str):
        items = value.split(',')
    else:
        items = list(value)
    return [str(item).strip() for item in items if str(item).strip()]


def resolve_all_recipients(recipients):
    """Resolve recipient tokens to a deduplicated list of email addresses.

    Args:
        recipients: A list of tokens or a comma-separated string. Each
            token is a direct email address or a resolver-aware address
            (e.g. ``admins@group.local``).

    Returns:
        Deduplicated list of resolved email addresses.
    """
    resolved = []
    seen = set()
    for addr in as_email_list(recipients):
        for email in RecipientResolverRegistry.resolve(addr):
            if email not in seen:
                seen.add(email)
                resolved.append(email)
    return resolved


def chunk_list(lst, size):
    """Split a list into chunks of the given size.

    Args:
        lst: The list to split.
        size: Maximum chunk size.

    Returns:
        List of sublists.
    """
    if size <= 0:
        return [lst]
    return [lst[i:i + size] for i in range(0, len(lst), size)]


def rewrite_inline_images(html):
    """Rewrite inline image URLs to ``cid:`` references.

    The WYSIWYG editor embeds uploaded images as
    ``<img src=".../preview-file/<pk>">``. For self-contained emails these
    must reference the attached inline image by Content-ID instead.

    Args:
        html: The HTML body.

    Returns:
        HTML with ``preview-file`` image URLs rewritten to ``cid:img_<pk>``.
    """
    if not html:
        return html

    def _repl(match):
        pk = match.group(2)
        return f'src="cid:img_{pk}"'

    return INLINE_IMG_RE.sub(_repl, html)


def extract_inline_pks(html):
    """Return the AttachedFile pks referenced by inline images in ``html``."""
    if not html:
        return []
    return [match.group(2) for match in INLINE_IMG_RE.finditer(html)]


def attach_inline_images(msg, pks):
    """Attach the given AttachedFiles inline with a matching Content-ID.

    Args:
        msg: The EmailMessage being built.
        pks: Iterable of AttachedFile primary keys referenced in the body.
    """
    for pk in pks:
        att = AttachedFile.objects.filter(pk=pk).first()
        if att is None or not att.file:
            continue
        try:
            data = att.file.read()
        except (OSError, ValueError):
            continue
        mime_image = MIMEImage(data)
        mime_image.add_header('Content-ID', f'img_{pk}')
        mime_image.add_header(
            'Content-Disposition', 'inline', filename=att.file.name)
        msg.attach(mime_image)


def link_body_attachments(instance):
    """Link inline AttachedFiles referenced in ``instance.message`` to it.

    Uploaded images start unattached (``object_id=0``); linking them to the
    saved object keeps them from being cleaned up as orphans. Sending does
    not depend on this — it attaches by the pks found in the body.
    """
    pks = extract_inline_pks(getattr(instance, 'message', ''))
    if not pks:
        return
    ct = ContentType.objects.get_for_model(instance)
    AttachedFile.objects.filter(pk__in=pks, object_id=0).update(
        content_type=ct, object_id=instance.pk)


def _get_attachments(notification):
    """Get AttachedFile objects linked to a notification."""
    ct = ContentType.objects.get_for_model(notification)
    return AttachedFile.objects.filter(
        content_type=ct, object_id=notification.pk)


def html_to_text(html):
    """Produce a readable plain-text version of an HTML body."""
    text = strip_tags(html or '')
    text = unescape(text)
    lines = [line.strip() for line in text.splitlines()]
    return '\n'.join(line for line in lines if line)


def filter_promotional_recipients(emails):
    """Drop suppressed (and, if opt-in is required, non-consented) addresses.

    Applied only to promotional email and newsletters; transactional mail
    ignores the suppression list.
    """
    if not emails:
        return []
    suppressed = suppressed_emails(emails)
    result = [e for e in emails if e not in suppressed]
    if ASYNC_NOTIFICATION_REQUIRE_OPTIN:
        allowed = consented_emails(result)
        result = [e for e in result if e in allowed]
    return result


def _throttle_interval():
    """Seconds to wait between messages to honor the rate limit (0 = none)."""
    rate = ASYNC_NOTIFICATION_RATE_LIMIT
    return 60.0 / rate if rate and rate > 0 else 0


def _promotional_extras(email, list_id=None):
    """Return (footer_html, headers) for a promotional message to ``email``.

    Headers carry the RFC 8058 one-click unsubscribe plus bulk markers; the
    footer carries the visible unsubscribe link and mailing address.
    """
    headers, url = unsubscribe_headers(email)
    headers['Precedence'] = 'bulk'
    headers['Auto-Submitted'] = 'auto-generated'
    if list_id:
        headers['List-Id'] = list_id
    footer = render_to_string('async_notification/_email_footer.html', {
        'unsubscribe_url': url,
        'mailing_address': ASYNC_NOTIFICATION_MAILING_ADDRESS,
    })
    return footer, headers


def _make_message(subject, html_body, to, connection, bcc=None, cc=None,
                  headers=None):
    """Build a multipart/alternative message (plain text + HTML).

    Inline ``cid:`` images referenced in ``html_body`` are attached with a
    matching Content-ID.
    """
    text_body = html_to_text(html_body)
    inline_pks = extract_inline_pks(html_body)
    final_html = rewrite_inline_images(html_body)
    msg = EmailMultiAlternatives(
        subject, text_body, to=to, bcc=bcc or [], cc=cc or [],
        connection=connection, headers=headers or None)
    msg.attach_alternative(final_html, 'text/html')
    attach_inline_images(msg, inline_pks)
    return msg


def build_email_message(notification, batch, connection=None,
                        include_extra=True, unsubscribe_email=None):
    """Build a message from a notification for a batch of recipients.

    Sends multipart/alternative (plain text + HTML), applies the configured
    base template, embeds inline ``cid:`` images, and — for promotional mail
    (``unsubscribe_email`` set) — appends the unsubscribe footer and the
    RFC 8058 / bulk headers.

    Args:
        notification: EmailNotification instance.
        batch: List of recipient email addresses.
        connection: Optional SMTP connection to reuse.
        include_extra: Whether to include bcc/cc (only the first batch does).
        unsubscribe_email: When set (promotional, one recipient per message),
            adds one-click unsubscribe headers + footer for that address.

    Returns:
        EmailMultiAlternatives instance ready to send.
    """
    bcc_list = []
    cc_list = []
    if include_extra:
        bcc_list = as_email_list(notification.bcc)
        if ASYNC_BCC:
            bcc_list += as_email_list(ASYNC_BCC)
        cc_list = as_email_list(notification.cc)
        if ASYNC_CC:
            cc_list += as_email_list(ASYNC_CC)

    html_body = notification.message
    headers = None
    if unsubscribe_email:
        footer, headers = _promotional_extras(unsubscribe_email)
        html_body = html_body + footer
    if notification.base_template:
        html_body = wrap_in_base_template(html_body, notification.base_template)

    msg = _make_message(notification.subject, html_body, batch, connection,
                        bcc=bcc_list, cc=cc_list, headers=headers)

    # Explicit non-inline attachments linked to this notification.
    for att in _get_attachments(notification):
        if not att.is_inline:
            msg.attach_file(att.file.path)

    return msg


def retry_delay_for(notification):
    """Exponential backoff delay (seconds) for the next retry."""
    exponent = max(0, notification.retry_count - 1)
    return ASYNC_NOTIFICATION_RETRY_DELAY * (2 ** exponent)


def _reschedule_retry(notification):
    """Ask the backend to re-attempt a failed send after a backoff delay.

    The Celery backend re-enqueues with a countdown; the sync backend is a
    no-op because the cron command picks pending notifications up again.
    """
    from djgentelella.async_notification.backends import get_backend

    backend = get_backend()
    retry = getattr(backend, 'retry', None)
    if callable(retry):
        retry(notification.pk, retry_delay_for(notification))


def _claim_notification(notification_pk):
    """Atomically transition a notification to 'sending' and return it.

    Uses ``select_for_update`` so that concurrent callers (the cron command,
    the immediate-send signal, and an at-least-once Celery redelivery) cannot
    all pass a plain status check and send duplicate copies: exactly one caller
    flips a claimable row to 'sending'; the rest get ``None`` and stop.

    Returns the claimed notification, or ``None`` if it does not exist, is
    already terminal ('sent'/'cancelled'), or is already being sent by another
    worker.
    """
    with transaction.atomic():
        try:
            notification = (EmailNotification.objects
                            .select_for_update()
                            .get(pk=notification_pk))
        except EmailNotification.DoesNotExist:
            logger.error('EmailNotification %s does not exist', notification_pk)
            return None
        if notification.status in ('sent', 'cancelled', 'sending'):
            return None
        notification.status = 'sending'
        notification.last_attempt = timezone.now()
        notification.save(update_fields=['status', 'last_attempt'])
        return notification


def do_send_notification(notification_pk):
    """Send an email notification. Core send logic.

    Resolves recipients, batches them, sends, and updates status.
    Handles retries with exponential backoff up to the notification's
    ``max_retries``.

    Args:
        notification_pk: Primary key of the EmailNotification to send.
    """
    notification = _claim_notification(notification_pk)
    if notification is None:
        return

    try:
        recipients = resolve_all_recipients(notification.recipients)
        # Promotional mail honors the suppression list (and opt-in if required)
        # and goes one message per recipient (each with its own unsubscribe).
        promotional = notification.is_promotional
        if promotional:
            recipients = filter_promotional_recipients(recipients)
        notification.recipients_raw = ', '.join(recipients)
        notification.save(update_fields=['recipients_raw'])

        # Resume: skip addresses already delivered on a previous attempt so a
        # retry after a mid-batch failure does not re-send earlier batches.
        already = set(notification.sent_recipients or [])
        pending = [r for r in recipients if r not in already]

        if not pending:
            notification.status = 'sent'
            notification.save(update_fields=['status'])
            return

        if promotional or notification.send_individually:
            batches = [[r] for r in pending]
        else:
            batches = chunk_list(pending, ASYNC_NOTIFICATION_MAX_PER_MAIL)

        # bcc/cc go only with the very first batch ever sent, so those
        # recipients get exactly one copy across all batches and retries.
        first_send = not already
        interval = _throttle_interval()

        connection = get_connection()
        connection.open()
        try:
            for index, batch in enumerate(batches):
                unsub = batch[0] if promotional else None
                msg = build_email_message(
                    notification, batch, connection=connection,
                    include_extra=(first_send and index == 0),
                    unsubscribe_email=unsub)
                msg.send()
                # Persist progress after each delivered batch.
                already.update(batch)
                notification.sent_recipients = list(already)
                notification.save(update_fields=['sent_recipients'])
                if interval:
                    time.sleep(interval)
        finally:
            connection.close()

        notification.status = 'sent'
        notification.error_message = ''
        notification.save(update_fields=['status', 'error_message'])

    except Exception as e:
        logger.exception('Error sending notification %s', notification_pk)
        notification.retry_count += 1
        notification.error_message = str(e)

        limit = notification.max_retries or ASYNC_NOTIFICATION_MAX_RETRIES
        if notification.retry_count >= limit:
            notification.status = 'failed'
            notification.save(update_fields=[
                'retry_count', 'error_message', 'status'])
        else:
            notification.status = 'pending'
            notification.save(update_fields=[
                'retry_count', 'error_message', 'status'])
            _reschedule_retry(notification)


def compute_newsletter_recipients(newsletter):
    """Resolve the full recipient list for a newsletter.

    Combines the free-text ``recipients`` field (raw addresses, groups,
    content-type references) with recipients derived from the template's
    registered base model + stored filters.

    The base model's filters (e.g. "only active users", "exclude X") apply
    to *every* recipient that belongs to that model, not just the ones the
    interface itself resolved: a free-text entry that happens to expand to
    addresses of the same model (e.g. a Django group full of ``auth.User``
    members, via ``@group.local``) must still satisfy those filters. An
    address that does not belong to the base model at all (an external
    email typed by hand) has no "active"/"excluded" status to check, so it
    always passes through untouched.

    Args:
        newsletter: NewsLetter instance.

    Returns:
        Deduplicated list of email addresses.
    """
    from djgentelella.async_notification.interfaces import get_basemodel_info

    recipients = resolve_all_recipients(newsletter.recipients)

    template = newsletter.template
    model_base = getattr(template, 'model_base', '') if template else ''
    if model_base:
        info = get_basemodel_info(model_base)
        if info:
            interface = info[2]()
            allowed = set(interface.get_recipients(
                newsletter.filters_querystring))
            model_emails = set(
                e for e in interface.model.objects.values_list(
                    interface.email_field, flat=True) if e)
            # Drop merged recipients that belong to this model but were
            # filtered out of it; addresses outside the model are untouched.
            recipients = [r for r in recipients
                         if r not in model_emails or r in allowed]
            seen = set(recipients)
            for email in allowed:
                if email not in seen:
                    seen.add(email)
                    recipients.append(email)
    return recipients


def _claim_newsletter_task(newsletter_task_pk):
    """Atomically transition a newsletter task to 'sending' and return it.

    Same duplicate-protection as :func:`_claim_notification`: exactly one
    caller claims a claimable task; concurrent callers get ``None``.
    """
    with transaction.atomic():
        try:
            task = (NewsLetterTask.objects
                    .select_for_update()
                    .select_related('newsletter')
                    .get(pk=newsletter_task_pk))
        except NewsLetterTask.DoesNotExist:
            logger.error('NewsLetterTask %s does not exist', newsletter_task_pk)
            return None
        if task.status in ('sent', 'revoked', 'sending'):
            return None
        task.status = 'sending'
        task.save(update_fields=['status'])
        return task


def do_send_newsletter(newsletter_task_pk):
    """Send a newsletter task.

    Sends one promotional message per recipient (each with its own one-click
    unsubscribe), honoring the suppression list. Delivery progress is persisted
    per recipient in ``task.sent_recipients`` so a re-run after a mid-list
    failure resumes with the pending recipients instead of re-sending to
    already-delivered ones.

    Args:
        newsletter_task_pk: Primary key of the NewsLetterTask.
    """
    task = _claim_newsletter_task(newsletter_task_pk)
    if task is None:
        return

    newsletter = task.newsletter

    try:
        # Newsletters are promotional: honor the suppression list and send one
        # message per recipient, each with its own one-click unsubscribe.
        recipients = filter_promotional_recipients(
            compute_newsletter_recipients(newsletter))

        # Resume: skip recipients already delivered on a previous run so a
        # re-run after a mid-list failure does not re-send to them.
        already = set(task.sent_recipients or [])
        pending = [r for r in recipients if r not in already]

        if not pending:
            task.status = 'sent'
            task.error_message = ''
            task.save(update_fields=['status', 'error_message'])
            return

        # Use custom SMTP if configured
        connection = None
        if ASYNC_NEWSLETTER_SEVER_CONFIGS:
            config = ASYNC_NEWSLETTER_SEVER_CONFIGS
            if isinstance(config, dict) and 'host' in config:
                connection = get_connection(
                    host=config.get('host'),
                    port=config.get('port', 587),
                    username=config.get('username', ''),
                    password=config.get('password', ''),
                    use_tls=config.get('use_tls', True),
                )

        if connection is None:
            connection = get_connection()

        bcc_list = as_email_list(newsletter.bcc)
        cc_list = as_email_list(newsletter.cc)
        interval = _throttle_interval()
        # List-level bcc/cc ride only the very first message ever sent, so on a
        # resume (already non-empty) they are not re-sent.
        first_message = not already

        connection.open()
        try:
            for email in pending:
                footer, headers = _promotional_extras(
                    email, list_id=ASYNC_NOTIFICATION_LIST_ID)
                html_body = newsletter.message + footer
                if newsletter.base_template:
                    html_body = wrap_in_base_template(
                        html_body, newsletter.base_template)
                msg = _make_message(
                    newsletter.subject, html_body, [email], connection,
                    bcc=bcc_list if first_message else [],
                    cc=cc_list if first_message else [],
                    headers=headers)

                if newsletter.attached_file:
                    try:
                        msg.attach_file(newsletter.attached_file.path)
                    except Exception:
                        logger.exception(
                            'Could not attach %s to newsletter task %s',
                            newsletter.attached_file, newsletter_task_pk)

                msg.send()
                first_message = False
                # Persist progress after each delivered message.
                already.add(email)
                task.sent_recipients = list(already)
                task.save(update_fields=['sent_recipients'])
                if interval:
                    time.sleep(interval)
        finally:
            connection.close()

        task.status = 'sent'
        task.error_message = ''
        task.save(update_fields=['status', 'error_message'])

    except Exception as e:
        logger.exception('Error sending newsletter task %s',
                         newsletter_task_pk)
        task.status = 'failed'
        task.error_message = str(e)
        task.save(update_fields=['status', 'error_message'])


def send_email_from_template(code, recipient, context, enqueued=True,
                             user=None, upfile=None, bcc='', cc=''):
    """Create and optionally send an email from a registered template.

    Args:
        code: EmailTemplate code (slug).
        recipient: Comma-separated recipient string or list.
        context: Dict of template context variables.
        enqueued: If True, queued for backend processing.
            If False, triggers immediate send via signal.
        user: Optional User instance to associate with the notification.
        upfile: Optional file to attach.
        bcc: Additional BCC addresses (string or list).
        cc: Additional CC addresses (string or list).

    Returns:
        The created EmailNotification instance.

    Raises:
        EmailTemplate.DoesNotExist: If template code is not found.
    """
    template = EmailTemplate.objects.get(code=code)

    subject_tpl = Template(template.subject)
    message_tpl = Template(template.message)
    ctx = Context(context)

    rendered_subject = subject_tpl.render(ctx)
    rendered_message = message_tpl.render(ctx)

    all_bcc = as_email_list(template.bcc) + as_email_list(bcc)
    all_cc = as_email_list(template.cc) + as_email_list(cc)

    notification = EmailNotification.objects.create(
        subject=rendered_subject,
        message=rendered_message,
        recipients=as_email_list(recipient),
        bcc=all_bcc,
        cc=all_cc,
        base_template=template.base_template,
        enqueued=enqueued,
        user=user,
    )

    if upfile:
        ct = ContentType.objects.get_for_model(EmailNotification)
        AttachedFile.objects.create(
            content_type=ct,
            object_id=notification.pk,
            file=upfile,
        )

    return notification
