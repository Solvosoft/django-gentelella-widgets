from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _

from djgentelella.settings import USER_MODEL_BASE


def validate_recipient_list(value):
    """Validate a JSON list of recipient tokens.

    Each token must be either a valid email address or a resolver token
    of the form ``identifier@suffix`` whose suffix is registered in the
    :class:`RecipientResolverRegistry` (e.g. ``admins@group.local``).
    Empty lists are allowed.
    """
    from djgentelella.async_notification.resolvers import (
        RecipientResolverRegistry,
    )

    if not value:
        return
    if not isinstance(value, list):
        raise ValidationError(_('Recipients must be a list.'))
    for token in value:
        token = (token or '').strip()
        if not token:
            continue
        try:
            validate_email(token)
            continue
        except ValidationError:
            pass
        if '@' in token:
            suffix = token.rsplit('@', 1)[1]
            if RecipientResolverRegistry.has_resolver(suffix):
                continue
        raise ValidationError(
            _('Invalid recipient: %(token)s') % {'token': token})


class EmailTemplate(models.Model):
    """Reusable email template with placeholders for dynamic content."""
    code = models.SlugField(
        max_length=150, unique=True, verbose_name=_('Code'),
        help_text=_('Unique identifier for this template'))
    subject = models.CharField(
        max_length=500, verbose_name=_('Subject'))
    message = models.TextField(
        verbose_name=_('Message'),
        help_text=_('HTML content with Django template syntax'))
    bcc = models.TextField(
        blank=True, default='', verbose_name=_('BCC'))
    cc = models.TextField(
        blank=True, default='', verbose_name=_('CC'))
    context_code = models.CharField(
        max_length=150, blank=True, default='',
        verbose_name=_('Context Code'),
        help_text=_('Registered context code for variable suggestions'))
    base_template = models.CharField(
        max_length=150, blank=True, default='',
        verbose_name=_('Base Template'),
        help_text=_('Base template key from settings to wrap the email content'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Email Template')
        verbose_name_plural = _('Email Templates')

    def __str__(self):
        return f'{self.code} - {self.subject}'


class EmailNotification(models.Model):
    """An email notification queued for sending."""
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('queued', _('Queued')),
        ('sending', _('Sending')),
        ('sent', _('Sent')),
        ('failed', _('Failed')),
        ('cancelled', _('Cancelled')),
    ]

    subject = models.CharField(
        max_length=500, verbose_name=_('Subject'))
    message = models.TextField(
        verbose_name=_('Message'))
    recipients = models.JSONField(
        default=list, blank=True, validators=[validate_recipient_list],
        verbose_name=_('Recipients'),
        help_text=_('List of email addresses or group references'))
    bcc = models.JSONField(
        default=list, blank=True, validators=[validate_recipient_list],
        verbose_name=_('BCC'))
    cc = models.JSONField(
        default=list, blank=True, validators=[validate_recipient_list],
        verbose_name=_('CC'))
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending',
        verbose_name=_('Status'))
    base_template = models.CharField(
        max_length=150, blank=True, default='',
        verbose_name=_('Base Template'),
        help_text=_('Base template key from settings to wrap the email body'))
    recipients_raw = models.TextField(
        blank=True, default='', verbose_name=_('Resolved Recipients'),
        help_text=_('Resolved email addresses after processing'))
    sent_recipients = models.JSONField(
        default=list, blank=True, verbose_name=_('Delivered Recipients'),
        help_text=_('Addresses already delivered; a retry resumes from here '
                    'instead of re-sending already-delivered batches'))
    retry_count = models.IntegerField(
        default=0, verbose_name=_('Retry Count'))
    max_retries = models.IntegerField(
        default=3, verbose_name=_('Max Retries'),
        help_text=_('Maximum number of send attempts before failing'))
    last_attempt = models.DateTimeField(
        null=True, blank=True, verbose_name=_('Last Attempt'))
    error_message = models.TextField(
        blank=True, default='', verbose_name=_('Error Message'))
    enqueued = models.BooleanField(
        default=True, verbose_name=_('Enqueued'),
        help_text=_('If True, processed by backend/cron. '
                    'If False, sent immediately via signal.'))
    send_individually = models.BooleanField(
        default=False, verbose_name=_('Send Individually'),
        help_text=_('Send one email per recipient instead of batching'))
    is_promotional = models.BooleanField(
        default=False, verbose_name=_('Promotional'),
        help_text=_('Marketing/promotional email: adds one-click unsubscribe '
                    'headers, honors the suppression list, and is sent one '
                    'message per recipient. Leave off for transactional mail '
                    '(password resets, receipts, etc.).'))
    user = models.ForeignKey(
        USER_MODEL_BASE, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Created By'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Email Notification')
        verbose_name_plural = _('Email Notifications')
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f'{self.subject} ({self.status})'

    @property
    def sent(self):
        """Backwards-compatible flag: True once the email has been sent."""
        return self.status == 'sent'


class AttachedFile(models.Model):
    """File attachment linked to any model via GenericForeignKey."""
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE,
        verbose_name=_('Content Type'))
    object_id = models.PositiveIntegerField(
        verbose_name=_('Object ID'))
    content_object = GenericForeignKey('content_type', 'object_id')
    file = models.FileField(
        upload_to='async_notification/attachments/%Y/%m/%d/',
        verbose_name=_('File'))
    is_inline = models.BooleanField(
        default=False, verbose_name=_('Is Inline'),
        help_text=_('If True, embedded as inline image (cid:)'))
    content_id = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name=_('Content ID'),
        help_text=_('Content-ID for inline attachments'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Attached File')
        verbose_name_plural = _('Attached Files')

    def __str__(self):
        return f'{self.file.name}'


class NewsLetterTemplate(models.Model):
    """Template for newsletters with reusable content structure."""
    title = models.CharField(
        max_length=500, verbose_name=_('Title'))
    slug = models.SlugField(
        max_length=150, unique=True, verbose_name=_('Slug'))
    message = models.TextField(
        verbose_name=_('Message'),
        help_text=_('HTML content for the newsletter template'))
    model_base = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name=_('Model Base'),
        help_text=_('Key from ASYNC_NEWS_BASE_MODELS settings'))
    base_template = models.CharField(
        max_length=150, blank=True, default='',
        verbose_name=_('Base Template'),
        help_text=_('Base template key from settings to wrap the content'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Newsletter Template')
        verbose_name_plural = _('Newsletter Templates')

    def __str__(self):
        return self.title


class NewsLetter(models.Model):
    """A newsletter composed from a template, ready to be scheduled."""
    template = models.ForeignKey(
        NewsLetterTemplate, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Template'))
    subject = models.CharField(
        max_length=500, verbose_name=_('Subject'))
    message = models.TextField(
        verbose_name=_('Message'))
    recipients = models.JSONField(
        default=list, blank=True, validators=[validate_recipient_list],
        verbose_name=_('Recipients'),
        help_text=_('List of email addresses or group references'))
    bcc = models.JSONField(
        default=list, blank=True, validators=[validate_recipient_list],
        verbose_name=_('BCC'))
    cc = models.JSONField(
        default=list, blank=True, validators=[validate_recipient_list],
        verbose_name=_('CC'))
    base_template = models.CharField(
        max_length=150, blank=True, default='',
        verbose_name=_('Base Template'),
        help_text=_('Base template key from settings to wrap the content'))
    attached_file = models.FileField(
        upload_to='async_notification/newsletter/%Y/%m/%d/',
        blank=True, null=True, verbose_name=_('Attached File'))
    created_by = models.ForeignKey(
        USER_MODEL_BASE, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Created By'))
    filters_querystring = models.TextField(
        blank=True, default='', verbose_name=_('Filters Querystring'),
        help_text=_('Querystring for filtering recipients'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Newsletter')
        verbose_name_plural = _('Newsletters')

    def __str__(self):
        return self.subject


class NewsLetterTask(models.Model):
    """Scheduled sending task for a newsletter."""
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('scheduled', _('Scheduled')),
        ('sending', _('Sending')),
        ('sent', _('Sent')),
        ('failed', _('Failed')),
        ('revoked', _('Revoked')),
    ]

    newsletter = models.ForeignKey(
        NewsLetter, on_delete=models.CASCADE,
        related_name='tasks', verbose_name=_('Newsletter'))
    send_date = models.DateTimeField(
        verbose_name=_('Send Date'))
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending',
        verbose_name=_('Status'))
    celery_task_id = models.CharField(
        max_length=255, null=True, blank=True,
        verbose_name=_('Celery Task ID'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-send_date']
        verbose_name = _('Newsletter Task')
        verbose_name_plural = _('Newsletter Tasks')

    def __str__(self):
        return f'{self.newsletter.subject} - {self.send_date} ({self.status})'


class EmailSuppression(models.Model):
    """An address that must not receive promotional email (opt-out list).

    Populated by one-click unsubscribes, complaint/bounce webhooks, or
    manually. Promotional sends and newsletters skip suppressed addresses;
    transactional email ignores this list.
    """
    REASON_CHOICES = [
        ('unsubscribe', _('Unsubscribed')),
        ('complaint', _('Spam complaint')),
        ('bounce', _('Hard bounce')),
        ('manual', _('Manual')),
    ]
    email = models.EmailField(
        unique=True, verbose_name=_('Email'))
    reason = models.CharField(
        max_length=20, choices=REASON_CHOICES, default='unsubscribe',
        verbose_name=_('Reason'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Email Suppression')
        verbose_name_plural = _('Email Suppressions')

    def __str__(self):
        return f'{self.email} ({self.reason})'


class EmailConsent(models.Model):
    """Optional opt-in record for an address.

    Only enforced when ``ASYNC_NOTIFICATION_REQUIRE_OPTIN`` is True; then
    promotional sends only reach addresses with ``granted=True``.
    """
    email = models.EmailField(
        unique=True, verbose_name=_('Email'))
    granted = models.BooleanField(
        default=True, verbose_name=_('Granted'))
    source = models.CharField(
        max_length=150, blank=True, default='', verbose_name=_('Source'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Email Consent')
        verbose_name_plural = _('Email Consents')

    def __str__(self):
        return f'{self.email} ({"granted" if self.granted else "revoked"})'


def suppressed_emails(emails):
    """Return the subset of ``emails`` that are on the suppression list."""
    if not emails:
        return set()
    return set(EmailSuppression.objects.filter(
        email__in=emails).values_list('email', flat=True))


def consented_emails(emails):
    """Return the subset of ``emails`` with a granted consent record."""
    if not emails:
        return set()
    return set(EmailConsent.objects.filter(
        email__in=emails, granted=True).values_list('email', flat=True))
