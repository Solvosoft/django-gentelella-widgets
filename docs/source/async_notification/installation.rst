Installation & Setup
===========================

Requirements
--------------

- Django 4.2+
- Django REST Framework
- ``djgentelella`` (core package)

Optional (pick one for async sending):

- **Celery** — for task-queue-based async sending (Redis/RabbitMQ broker required).
- **django-tasks** — for Django 6 native background tasks (no external broker needed).

If neither is installed, notifications are sent synchronously via the ``process_notifications`` cron command.

See :doc:`backends` for full setup instructions.

Adding to INSTALLED_APPS
---------------------------

Add ``djgentelella.async_notification`` to your ``INSTALLED_APPS``:

.. code:: python

    INSTALLED_APPS = [
        ...,
        'djgentelella',
        'rest_framework',
        'djgentelella.async_notification',
    ]

Running Migrations
---------------------

.. code:: bash

    python manage.py migrate

This creates the following database tables:

- ``async_notification_emailtemplate``
- ``async_notification_emailnotification``
- ``async_notification_attachedfile``
- ``async_notification_newslettertemplate``
- ``async_notification_newsletter``
- ``async_notification_newslettertask``

URL Configuration
--------------------

Include the async_notification URLs in your project's ``urls.py``:

.. code:: python

    from django.urls import path, include

    urlpatterns = [
        ...,
        path('async_notification/',
             include('djgentelella.async_notification.urls')),
    ]

The module registers the following URL patterns:

- ``objapi/`` - DRF router for all API ViewSets
- ``email-notifications/`` - Email notification management page
- ``email-templates/`` - Email template management page
- ``newsletters/`` - Newsletter management page
- ``newsletter-templates/`` - Newsletter template management page
- ``newsletter-tasks/`` - Newsletter task management page
- ``autocomplete/`` - Recipient autocomplete endpoint
- ``model-fields/`` - Model field introspection endpoint
- ``upload-image/`` - Image upload for TinyMCE editor
- ``upload-video/`` - Video upload for TinyMCE editor
- ``preview-file/<int:pk>/`` - Serve an attached file
- ``reassociate-files/`` - Reassociate uploaded files with a real object
- ``preview-template/`` - Template preview rendering

Permissions
--------------

All views require authentication (``@login_required`` for HTML views, ``SessionAuthentication`` for API).
The API ViewSets use ``AuthAllPermBaseObjectManagement`` with Django model permissions:

- ``async_notification.view_emailnotification``
- ``async_notification.add_emailnotification``
- ``async_notification.change_emailnotification``
- ``async_notification.delete_emailnotification``

And equivalents for ``emailtemplate``, ``newslettertemplate``, ``newsletter``, and ``newslettertask``.

Make sure to assign the appropriate permissions to users or groups that need access to the management UI.
