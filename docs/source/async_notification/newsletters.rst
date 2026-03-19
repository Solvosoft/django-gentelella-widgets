Newsletters
===========================

The newsletter system allows composing newsletters from templates and scheduling them for delivery.

Newsletter Templates
-----------------------

Newsletter templates provide reusable HTML content structures. They can optionally reference a model base
for dynamic content.

.. code:: python

    from djgentelella.async_notification.models import NewsLetterTemplate

    NewsLetterTemplate.objects.create(
        title='Monthly Digest',
        slug='monthly-digest',
        message=(
            '<h1>Monthly Digest</h1>'
            '<p>Here are the highlights from this month.</p>'
        ),
        model_base='customers',  # Key from ASYNC_NEWS_BASE_MODELS
    )

Creating Newsletters
-----------------------

A newsletter is composed from a template with specific recipients:

.. code:: python

    from djgentelella.async_notification.models import (
        NewsLetterTemplate, NewsLetter
    )

    template = NewsLetterTemplate.objects.get(slug='monthly-digest')

    newsletter = NewsLetter.objects.create(
        template=template,
        subject='January 2026 Monthly Digest',
        message=template.message,  # Or customized content
        recipients='subscribers@group.local, vip@group.local',
        created_by=user,
    )

Recipients support the same resolver syntax as email notifications (see :doc:`resolvers`).

Scheduling Newsletter Tasks
-------------------------------

Newsletter delivery is controlled through ``NewsLetterTask`` objects:

.. code:: python

    from django.utils import timezone
    from djgentelella.async_notification.models import NewsLetterTask

    task = NewsLetterTask.objects.create(
        newsletter=newsletter,
        send_date=timezone.now() + timezone.timedelta(days=7),
    )

**Task lifecycle:**

1. Task is created with ``status='pending'``.
2. The backend ``schedule()`` method is called (either Celery beat or cron-based).
3. When ``send_date`` arrives, the task is picked up and ``status`` transitions to ``sending``.
4. After successful delivery, ``status`` becomes ``sent``.
5. On failure, ``status`` becomes ``failed``.

**Revoking a task:**

Tasks with ``pending`` or ``scheduled`` status can be revoked:

.. code:: python

    from djgentelella.async_notification.backends import get_backend

    backend = get_backend()
    backend.revoke(task.pk)
    # Task status is now 'revoked'

Custom SMTP for Newsletters
-------------------------------

Newsletters can use a separate SMTP server from regular notifications. Configure it in settings:

.. code:: python

    ASYNC_NEWSLETTER_SEVER_CONFIGS = {
        'host': 'smtp.newsletter-provider.com',
        'port': 587,
        'username': 'newsletters@example.com',
        'password': 'secret',
        'use_tls': True,
    }

If not configured, newsletters use Django's default email backend.

File Attachments
-------------------

Newsletters support a single file attachment via the ``attached_file`` field:

.. code:: python

    newsletter = NewsLetter.objects.create(
        template=template,
        subject='Product Catalog',
        message='<p>Please find our latest catalog attached.</p>',
        recipients='subscribers@group.local',
        attached_file=uploaded_file,
        created_by=user,
    )

Preview Recipients
---------------------

The management UI provides a "Preview Recipients" action that resolves all recipient addresses
without sending any email. This is useful for verifying that group resolvers and email addresses
are configured correctly before scheduling a send.

The API endpoint is a ``GET`` request to ``/objapi/newsletter/<id>/preview_recipients/``,
which returns a JSON response with the resolved email list and count.
