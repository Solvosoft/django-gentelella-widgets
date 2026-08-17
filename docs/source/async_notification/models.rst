Models
===========================

The module defines six models for managing email templates, notifications, newsletters, and file attachments.

EmailTemplate
-----------------

Reusable email templates with Django template syntax for dynamic content.

**Fields:**

- ``code`` (SlugField, unique) - Unique identifier for the template (e.g., ``welcome``, ``password-reset``).
- ``subject`` (CharField) - Subject line, supports Django template variables.
- ``message`` (TextField) - HTML body content with Django template syntax.
- ``bcc`` (TextField) - Default BCC addresses for this template.
- ``cc`` (TextField) - Default CC addresses for this template.
- ``context_code`` (CharField) - Registered context code for variable suggestions in the editor.
- ``base_template`` (CharField) - Key from ``ASYNC_NOTIFICATION_BASE_TEMPLATES`` to wrap the email.
- ``created_at`` / ``updated_at`` - Timestamps.

.. code:: python

    from djgentelella.async_notification.models import EmailTemplate

    template = EmailTemplate.objects.create(
        code='order-confirmation',
        subject='Order #{{ order.id }} Confirmed',
        message='<h2>Thank you, {{ user.first_name }}!</h2>'
                '<p>Your order #{{ order.id }} is confirmed.</p>',
        context_code='order_confirmation',
        base_template='default',
    )

EmailNotification
---------------------

An email notification queued for sending. Created directly or via ``send_email_from_template()``.

**Fields:**

- ``subject`` (CharField) - Email subject.
- ``message`` (TextField) - Rendered HTML body.
- ``recipients`` (TextField) - Comma-separated email addresses or resolver references (e.g., ``admins@group.local``).
- ``bcc`` / ``cc`` (TextField) - Additional BCC/CC addresses.
- ``status`` (CharField) - One of: ``pending``, ``sending``, ``sent``, ``failed``.
- ``sent`` (BooleanField) - Whether the email was successfully sent.
- ``recipients_raw`` (TextField) - Resolved email addresses after processing.
- ``retry_count`` (IntegerField) - Number of send attempts.
- ``error_message`` (TextField) - Last error message if send failed.
- ``enqueued`` (BooleanField) - If ``True``, processed by the backend/cron. If ``False``, sent immediately via signal.
- ``send_individually`` (BooleanField) - Send one email per recipient instead of batching.
- ``user`` (ForeignKey to User) - The user who created this notification.
- ``created_at`` / ``updated_at`` - Timestamps.

**Status flow:**

``pending`` → ``sending`` → ``sent``

If sending fails and retries are exhausted: ``pending`` → ``sending`` → ``failed``

AttachedFile
-----------------

File attachment linked to any model via Django's ``GenericForeignKey``.

**Fields:**

- ``content_type`` / ``object_id`` / ``content_object`` - Generic foreign key.
- ``file`` (FileField) - The uploaded file.
- ``is_inline`` (BooleanField) - If ``True``, embedded as inline image (``cid:``).
- ``content_id`` (CharField) - Content-ID for inline attachments or upload session identifier.
- ``created_at`` - Timestamp.

NewsLetterTemplate
---------------------

Reusable newsletter template with HTML content.

**Fields:**

- ``title`` (CharField) - Display title.
- ``slug`` (SlugField, unique) - URL-friendly identifier.
- ``message`` (TextField) - HTML content.
- ``model_base`` (CharField) - Key from ``ASYNC_NEWS_BASE_MODELS`` settings.
- ``created_at`` / ``updated_at`` - Timestamps.

NewsLetter
--------------

A newsletter composed from a template, ready to be scheduled.

**Fields:**

- ``template`` (ForeignKey to NewsLetterTemplate) - Source template.
- ``subject`` (CharField) - Newsletter subject.
- ``message`` (TextField) - Final HTML content.
- ``recipients`` (TextField) - Comma-separated addresses or resolver references.
- ``bcc`` / ``cc`` (TextField) - Additional addresses.
- ``attached_file`` (FileField) - Optional file attachment.
- ``created_by`` (ForeignKey to User) - Creator.
- ``filters_querystring`` (TextField) - Querystring for filtering recipients.
- ``created_at`` / ``updated_at`` - Timestamps.

NewsLetterTask
-----------------

Scheduled sending task for a newsletter.

**Fields:**

- ``newsletter`` (ForeignKey to NewsLetter) - The newsletter to send.
- ``send_date`` (DateTimeField) - When to send.
- ``status`` (CharField) - One of: ``pending``, ``scheduled``, ``sending``, ``sent``, ``failed``, ``revoked``.
- ``celery_task_id`` (CharField) - Celery task ID if using Celery backend.
- ``created_at`` / ``updated_at`` - Timestamps.

**Status flow:**

``pending`` → ``scheduled`` → ``sending`` → ``sent``

Revoking: ``pending``/``scheduled`` → ``revoked``
