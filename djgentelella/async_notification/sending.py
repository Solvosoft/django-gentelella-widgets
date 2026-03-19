"""
Core email sending logic.

Handles recipient resolution, email construction, batching,
retry logic, and template-based sending.
"""

import logging

from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMessage, get_connection
from django.template import Template, Context
from django.utils.safestring import mark_safe

from djgentelella.async_notification.models import (
    EmailNotification, EmailTemplate, AttachedFile,
    NewsLetterTask,
)
from djgentelella.async_notification.resolvers import RecipientResolverRegistry
from djgentelella.async_notification.settings import (
    ASYNC_NOTIFICATION_MAX_PER_MAIL,
    ASYNC_NOTIFICATION_MAX_RETRIES,
    ASYNC_BCC,
    ASYNC_CC,
    ASYNC_NEWSLETTER_SEVER_CONFIGS,
)

logger = logging.getLogger(__name__)


def resolve_all_recipients(recipients_text):
    """Parse comma-separated recipients and resolve each via the registry.

    Args:
        recipients_text: Comma-separated string of email addresses
            or resolver-aware addresses (e.g., 'admins@group.local').

    Returns:
        Deduplicated list of resolved email addresses.
    """
    if not recipients_text or not recipients_text.strip():
        return []

    addresses = [addr.strip() for addr in recipients_text.split(',')
                 if addr.strip()]
    resolved = []
    seen = set()
    for addr in addresses:
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


def _get_attachments(notification):
    """Get AttachedFile objects linked to a notification."""
    ct = ContentType.objects.get_for_model(notification)
    return AttachedFile.objects.filter(
        content_type=ct, object_id=notification.pk)


def build_email_message(notification, batch, connection=None):
    """Build an EmailMessage from a notification for a batch of recipients.

    Args:
        notification: EmailNotification instance.
        batch: List of recipient email addresses.
        connection: Optional SMTP connection to reuse.

    Returns:
        EmailMessage instance ready to send.
    """
    bcc_list = []
    if notification.bcc:
        bcc_list = [b.strip() for b in notification.bcc.split(',') if b.strip()]
    if ASYNC_BCC:
        bcc_list += [b.strip() for b in ASYNC_BCC.split(',') if b.strip()]

    cc_list = []
    if notification.cc:
        cc_list = [c.strip() for c in notification.cc.split(',') if c.strip()]
    if ASYNC_CC:
        cc_list += [c.strip() for c in ASYNC_CC.split(',') if c.strip()]

    msg = EmailMessage(
        subject=notification.subject,
        body=notification.message,
        to=batch,
        bcc=bcc_list,
        cc=cc_list,
        connection=connection,
    )
    msg.content_subtype = 'html'

    attachments = _get_attachments(notification)
    for att in attachments:
        if att.is_inline and att.content_id:
            msg.attach(att.file.name, att.file.read(), 'image/png')
        else:
            msg.attach_file(att.file.path)

    return msg


def do_send_notification(notification_pk):
    """Send an email notification. Core send logic.

    Resolves recipients, batches them, sends, and updates status.
    Retries on failure up to notification.max_retries times.

    Args:
        notification_pk: Primary key of the EmailNotification to send.
    """
    try:
        notification = EmailNotification.objects.get(pk=notification_pk)
    except EmailNotification.DoesNotExist:
        logger.error('EmailNotification %s does not exist', notification_pk)
        return

    if notification.status == 'sent':
        return

    recipients = resolve_all_recipients(notification.recipients)
    notification.recipients_raw = ', '.join(recipients)
    notification.save(update_fields=['recipients_raw'])

    if not recipients:
        notification.status = 'sent'
        notification.sent = True
        notification.save(update_fields=['status', 'sent'])
        return

    if notification.send_individually:
        batches = [[r] for r in recipients]
    else:
        batches = chunk_list(recipients, ASYNC_NOTIFICATION_MAX_PER_MAIL)

    while notification.retry_count <= notification.max_retries:
        notification.status = 'sending'
        notification.save(update_fields=['status'])
        try:
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
            notification.sent = True
            notification.save(update_fields=['status', 'sent'])
            return

        except Exception as e:
            logger.exception('Error sending notification %s (attempt %s/%s)',
                             notification_pk, notification.retry_count + 1,
                             notification.max_retries + 1)
            notification.retry_count += 1
            notification.error_message = str(e)

            if notification.retry_count > notification.max_retries:
                notification.status = 'failed'
                notification.save(update_fields=[
                    'retry_count', 'error_message', 'status'])
                return

            notification.status = 'pending'
            notification.save(update_fields=[
                'retry_count', 'error_message', 'status'])


NEWSLETTER_BATCH_SIZE = 50


def do_send_newsletter_direct(newsletter_pk):
    """Send a newsletter directly without a NewsLetterTask, in batches of 50.

    Args:
        newsletter_pk: Primary key of the NewsLetter to send.

    Returns:
        Dict with keys 'sent' (int), 'total' (int), 'error' (str or None).
    """
    from djgentelella.async_notification.models import NewsLetter

    try:
        newsletter = NewsLetter.objects.get(pk=newsletter_pk)
    except NewsLetter.DoesNotExist:
        logger.error('NewsLetter %s does not exist', newsletter_pk)
        return {'sent': 0, 'total': 0, 'error': 'Newsletter not found'}

    try:
        recipients = resolve_all_recipients(newsletter.recipients)
        total = len(recipients)

        if not recipients:
            return {'sent': 0, 'total': 0, 'error': None}

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

        bcc_list = [b.strip() for b in newsletter.bcc.split(',') if b.strip()] if newsletter.bcc else []
        cc_list = [c.strip() for c in newsletter.cc.split(',') if c.strip()] if newsletter.cc else []

        batches = chunk_list(recipients, NEWSLETTER_BATCH_SIZE)
        sent = 0

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
                sent += len(batch)
        finally:
            connection.close()

        return {'sent': sent, 'total': total, 'error': None}

    except Exception as e:
        logger.exception('Error sending newsletter %s directly', newsletter_pk)
        return {'sent': 0, 'total': 0, 'error': str(e)}


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
        recipients = resolve_all_recipients(newsletter.recipients)

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

        bcc_list = []
        if newsletter.bcc:
            bcc_list = [b.strip() for b in newsletter.bcc.split(',')
                        if b.strip()]

        cc_list = []
        if newsletter.cc:
            cc_list = [c.strip() for c in newsletter.cc.split(',')
                       if c.strip()]

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
                              user=None, upfile=None, bcc='', cc='', max_retries=3):
    """Create and optionally send an email from a registered template.

    Args:
        code: EmailTemplate code (slug).
        recipient: Comma-separated recipient string.
        context: Dict of template context variables.
        enqueued: If True, queued for backend processing.
            If False, triggers immediate send via signal.
        user: Optional User instance to associate with the notification.
        upfile: Optional file to attach.
        bcc: Additional BCC addresses.
        cc: Additional CC addresses.

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

    if template.base_template:
        base_tpl = Template(template.base_template.message)
        rendered_message = base_tpl.render(Context({**context, 'body': mark_safe(rendered_message)}))

    all_bcc = template.bcc
    if bcc:
        all_bcc = f'{all_bcc}, {bcc}' if all_bcc else bcc

    all_cc = template.cc
    if cc:
        all_cc = f'{all_cc}, {cc}' if all_cc else cc

    notification = EmailNotification.objects.create(
        subject=rendered_subject,
        message=rendered_message,
        recipients=recipient,
        bcc=all_bcc,
        cc=all_cc,
        enqueued=enqueued,
        user=user,
        max_retries=max_retries,
    )

    if upfile:
        ct = ContentType.objects.get_for_model(EmailNotification)
        AttachedFile.objects.create(
            content_type=ct,
            object_id=notification.pk,
            file=upfile,
        )

    return notification
