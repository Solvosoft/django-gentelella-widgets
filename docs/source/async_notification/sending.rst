Sending Emails
===========================

The module provides multiple ways to send emails: directly from code using templates, through the management UI,
or via the cron-based processing command.

Sending from Code
--------------------

The primary API for sending emails from your application code is ``send_email_from_template()``.

.. code:: python

    from djgentelella.async_notification.sending import send_email_from_template

    # Send using a registered template
    notification = send_email_from_template(
        code='order-confirmation',
        recipient='customer@example.com',
        context={
            'user': {'first_name': 'John'},
            'order': {'id': 1234, 'total': '99.99'},
        },
    )

**Parameters:**

- ``code`` - The ``EmailTemplate.code`` slug to use.
- ``recipient`` - Comma-separated recipient string. Supports resolver addresses (e.g., ``admins@group.local``).
- ``context`` - Dict of template context variables for rendering subject and message.
- ``enqueued`` (default ``True``) - If ``True``, the notification is queued for backend/cron processing.
  If ``False``, it is sent immediately via a ``post_save`` signal.
- ``user`` - Optional User instance to associate with the notification.
- ``upfile`` - Optional file to attach.
- ``bcc`` / ``cc`` - Additional BCC/CC addresses.

**Returns:** The created ``EmailNotification`` instance.

Immediate vs Queued Sending
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When ``enqueued=False``, a ``post_save`` signal fires and the backend sends the email immediately:

.. code:: python

    # Send immediately (synchronous or via Celery, depending on backend)
    notification = send_email_from_template(
        code='password-reset',
        recipient='user@example.com',
        context={'user': user, 'reset_url': url},
        enqueued=False,
    )

When ``enqueued=True`` (default), the notification is stored with ``status='pending'`` and processed by the
``process_notifications`` management command or Celery beat scheduler.

Creating Notifications Directly
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can also create ``EmailNotification`` objects directly without using a template:

.. code:: python

    from djgentelella.async_notification.models import EmailNotification

    notification = EmailNotification.objects.create(
        subject='System Alert',
        message='<p>Server disk usage is above 90%.</p>',
        recipients='ops-team@example.com, devops@group.local',
        enqueued=True,
    )

Recipient Resolution
^^^^^^^^^^^^^^^^^^^^^^^

Recipients are resolved at send time. Comma-separated values are parsed individually:

- Plain email addresses (``user@example.com``) are used as-is.
- Resolver addresses (``admins@group.local``) are resolved through the registered resolver for that domain.

See :doc:`resolvers` for details on creating custom resolvers.

Batching
^^^^^^^^^^^

When sending to many recipients, emails are split into batches of ``ASYNC_NOTIFICATION_MAX_PER_MAIL`` (default 40).
A single SMTP connection is reused across all batches for efficiency.

If ``send_individually=True`` on the notification, each recipient gets a separate email.

Retry Logic
^^^^^^^^^^^^^^^

If sending fails, the notification's ``retry_count`` is incremented and the status is reset to ``pending``
for reprocessing. After ``ASYNC_NOTIFICATION_MAX_RETRIES`` (default 3) failures, the status is set to ``failed``
and the ``error_message`` field contains the last error.

Celery Integration
---------------------

If Celery is installed, two shared tasks are available in */djgentelella/async_notification/tasks.py*:

.. code:: python

    from djgentelella.async_notification.tasks import (
        send_email_task,
        send_newsletter_task,
    )

    # Queue a notification for async sending
    send_email_task.delay(notification.pk)

    # Queue a newsletter task
    send_newsletter_task.delay(newsletter_task.pk)

These tasks are automatically used when the Celery backend is active.

Signal-Based Sending
-----------------------

A ``post_save`` signal on ``EmailNotification`` handles immediate sends. When a notification is created with
``enqueued=False`` and ``status='pending'``, the signal triggers the configured backend's ``send()`` method.

An anti-recursion guard prevents the signal from firing during the send process itself.
