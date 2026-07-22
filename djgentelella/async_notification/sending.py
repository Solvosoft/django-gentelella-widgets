"""
Core email sending logic.

Handles recipient resolution, email construction, batching,
retry logic, and template-based sending.
"""

import logging
import re
from email.mime.image import MIMEImage

from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMessage, get_connection
from django.template import Template, Context
from django.utils import timezone

from djgentelella.async_notification.models import (
    EmailNotification, EmailTemplate, AttachedFile,
    NewsLetterTask,
)
from djgentelella.async_notification.preview import wrap_in_base_template
from djgentelella.async_notification.resolvers import RecipientResolverRegistry
from djgentelella.async_notification.settings import (
    ASYNC_NOTIFICATION_MAX_PER_MAIL,
    ASYNC_NOTIFICATION_MAX_RETRIES,
    ASYNC_NOTIFICATION_RETRY_DELAY,
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
    ``<img src=".../preview_file/<pk>">``. For self-contained emails these
    must reference the attached inline image by Content-ID instead.

    Args:
        html: The HTML body.

    Returns:
        HTML with ``preview_file`` image URLs rewritten to ``cid:img_<pk>``.
    """
    if not html:
        return html

    def _repl(match):
        pk = match.group(2)
        return f'src="cid:img_{pk}"'

    return INLINE_IMG_RE.sub(_repl, html)


def _get_attachments(notification):
    """Get AttachedFile objects linked to a notification."""
    ct = ContentType.objects.get_for_model(notification)
    return AttachedFile.objects.filter(
        content_type=ct, object_id=notification.pk)


def build_email_message(notification, batch, connection=None):
    """Build an EmailMessage from a notification for a batch of recipients.

    Applies the configured base template, rewrites inline images to
    ``cid:`` references, and attaches inline images with a matching
    Content-ID so the email is self-contained.

    Args:
        notification: EmailNotification instance.
        batch: List of recipient email addresses.
        connection: Optional SMTP connection to reuse.

    Returns:
        EmailMessage instance ready to send.
    """
    bcc_list = as_email_list(notification.bcc)
    if ASYNC_BCC:
        bcc_list += as_email_list(ASYNC_BCC)

    cc_list = as_email_list(notification.cc)
    if ASYNC_CC:
        cc_list += as_email_list(ASYNC_CC)

    body = notification.message
    if notification.base_template:
        body = wrap_in_base_template(body, notification.base_template)
    body = rewrite_inline_images(body)

    msg = EmailMessage(
        subject=notification.subject,
        body=body,
        to=batch,
        bcc=bcc_list,
        cc=cc_list,
        connection=connection,
    )
    msg.content_subtype = 'html'

    for att in _get_attachments(notification):
        if att.is_inline:
            mime_image = MIMEImage(att.file.read())
            mime_image.add_header('Content-ID', f'img_{att.pk}')
            mime_image.add_header(
                'Content-Disposition', 'inline', filename=att.file.name)
            msg.attach(mime_image)
        else:
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


def do_send_notification(notification_pk):
    """Send an email notification. Core send logic.

    Resolves recipients, batches them, sends, and updates status.
    Handles retries with exponential backoff up to the notification's
    ``max_retries``.

    Args:
        notification_pk: Primary key of the EmailNotification to send.
    """
    try:
        notification = EmailNotification.objects.get(pk=notification_pk)
    except EmailNotification.DoesNotExist:
        logger.error('EmailNotification %s does not exist', notification_pk)
        return

    if notification.status in ('sent', 'cancelled'):
        return

    notification.status = 'sending'
    notification.last_attempt = timezone.now()
    notification.save(update_fields=['status', 'last_attempt'])

    try:
        recipients = resolve_all_recipients(notification.recipients)
        notification.recipients_raw = ', '.join(recipients)
        notification.save(update_fields=['recipients_raw'])

        if not recipients:
            notification.status = 'sent'
            notification.save(update_fields=['status'])
            return

        if notification.send_individually:
            batches = [[r] for r in recipients]
        else:
            batches = chunk_list(recipients, ASYNC_NOTIFICATION_MAX_PER_MAIL)

        connection = get_connection()
        connection.open()
        try:
            for batch in batches:
                msg = build_email_message(notification, batch,
                                          connection=connection)
                msg.send()
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

    Combines the free-text ``recipients`` field with recipients derived
    from the template's registered base model + stored filters.

    Args:
        newsletter: NewsLetter instance.

    Returns:
        Deduplicated list of email addresses.
    """
    from djgentelella.async_notification.interfaces import get_basemodel_info

    recipients = resolve_all_recipients(newsletter.recipients)
    seen = set(recipients)

    template = newsletter.template
    model_base = getattr(template, 'model_base', '') if template else ''
    if model_base:
        info = get_basemodel_info(model_base)
        if info:
            interface = info[2]()
            for email in interface.get_recipients(
                    newsletter.filters_querystring):
                if email and email not in seen:
                    seen.add(email)
                    recipients.append(email)
    return recipients


def do_send_newsletter(newsletter_task_pk):
    """Send a newsletter task.

    Args:
        newsletter_task_pk: Primary key of the NewsLetterTask.
    """
    try:
        task = NewsLetterTask.objects.select_related('newsletter').get(
            pk=newsletter_task_pk)
    except NewsLetterTask.DoesNotExist:
        logger.error('NewsLetterTask %s does not exist', newsletter_task_pk)
        return

    if task.status in ('sent', 'revoked'):
        return

    task.status = 'sending'
    task.save(update_fields=['status'])

    newsletter = task.newsletter

    try:
        recipients = compute_newsletter_recipients(newsletter)

        if not recipients:
            task.status = 'sent'
            task.save(update_fields=['status'])
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

        batches = chunk_list(recipients, ASYNC_NOTIFICATION_MAX_PER_MAIL)

        connection.open()
        try:
            for batch in batches:
                msg = EmailMessage(
                    subject=newsletter.subject,
                    body=newsletter.message,
                    to=batch,
                    bcc=bcc_list,
                    cc=cc_list,
                    connection=connection,
                )
                msg.content_subtype = 'html'

                if newsletter.attached_file:
                    try:
                        msg.attach_file(newsletter.attached_file.path)
                    except Exception:
                        pass

                msg.send()
        finally:
            connection.close()

        task.status = 'sent'
        task.save(update_fields=['status'])

    except Exception as e:
        logger.exception('Error sending newsletter task %s',
                         newsletter_task_pk)
        task.status = 'failed'
        task.save(update_fields=['status'])


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
