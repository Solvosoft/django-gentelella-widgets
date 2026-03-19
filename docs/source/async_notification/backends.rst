Sending Backends
===========================

The async_notification module delegates the actual dispatch of notifications to a configurable
**backend**. Three backends are available:

.. list-table::
   :header-rows: 1
   :widths: 25 30 45

   * - Backend
     - Class path
     - When to use
   * - **Sync**
     - ``...backends.sync.SyncBackend``
     - Development, no task queue available. Use with the ``process_notifications`` cron command.
   * - **Celery**
     - ``...backends.celery.CeleryBackend``
     - Production with an existing Celery installation.
   * - **Django Tasks**
     - ``...backends.django_tasks.DjangoTasksBackend``
     - Production with Django 6 native background tasks (no Celery required).

Autodetection
--------------

When ``ASYNC_NOTIFICATION_BACKEND`` is ``None`` (the default), the module detects the best
available backend in this order:

1. **Celery** — if ``celery`` is importable **and** ``CELERY_BROKER_URL`` is set in ``settings.py``.
2. **Django Tasks** — if ``django.tasks`` is importable (Django 6+) **and** ``TASKS`` is set in ``settings.py``.
3. **Sync** — fallback. Emails are sent in the current process; use cron to drain the queue.

.. code:: python

    # Explicitly set a backend (optional — autodetect usually works)
    ASYNC_NOTIFICATION_BACKEND = 'djgentelella.async_notification.backends.celery.CeleryBackend'

    # or
    ASYNC_NOTIFICATION_BACKEND = 'djgentelella.async_notification.backends.django_tasks.DjangoTasksBackend'

    # or
    ASYNC_NOTIFICATION_BACKEND = 'djgentelella.async_notification.backends.sync.SyncBackend'

----

Sync Backend (Cron / No Task Queue)
-------------------------------------

The simplest setup. Emails are sent directly when the ``post_save`` signal fires or when
``process_notifications`` runs. No additional packages are needed.

**When is it used?**

- Autodetect selects it when neither Celery nor Django Tasks are configured.
- Always active as a fallback for development.

**Periodic processing with cron:**

.. code:: bash

    # Process pending notifications every 5 minutes
    */5 * * * * cd /path/to/project && python manage.py process_notifications

See :doc:`management_commands` for full details on ``process_notifications``.

----

Celery Backend
---------------

Dispatches each notification as a Celery shared task. This is the recommended backend for
projects that already use Celery.

Requirements
^^^^^^^^^^^^^

- ``celery`` package installed.
- A broker configured via ``CELERY_BROKER_URL`` (Redis, RabbitMQ, etc.).
- A running Celery worker.

Installation
^^^^^^^^^^^^^

.. code:: bash

    pip install celery redis   # or rabbitmq client

Settings
^^^^^^^^^

.. code:: python

    # settings.py

    CELERY_BROKER_URL = 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

    # Optional: explicit backend (autodetect picks Celery when CELERY_BROKER_URL is present)
    ASYNC_NOTIFICATION_BACKEND = 'djgentelella.async_notification.backends.celery.CeleryBackend'

Celery App Setup
^^^^^^^^^^^^^^^^^

Create a ``celery.py`` file in your Django project package (next to ``settings.py``):

.. code:: python

    # myproject/celery.py
    import os
    from celery import Celery

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

    app = Celery('myproject')
    app.config_from_object('django.conf:settings', namespace='CELERY')
    app.autodiscover_tasks()

And import it from ``__init__.py`` so it loads with Django:

.. code:: python

    # myproject/__init__.py
    from .celery import app as celery_app

    __all__ = ('celery_app',)

Starting the Worker
^^^^^^^^^^^^^^^^^^^^

.. code:: bash

    # Development
    celery -A myproject worker -l info

    # Production (recommended: use supervisor or systemd)
    celery -A myproject worker --loglevel=info --concurrency=4

How It Works
^^^^^^^^^^^^^

- Immediate send (``enqueued=False``): the ``post_save`` signal calls ``CeleryBackend.send()``,
  which enqueues ``send_email_task.delay(notification_pk)``.
- Queued send (``enqueued=True``): the notification stays ``pending`` until the Celery worker
  picks up the task or ``process_notifications`` is run.
- Newsletter scheduling: ``CeleryBackend.schedule()`` calls ``send_newsletter_task.apply_async()``
  with an ``eta`` equal to the task's ``send_date``.
- Revoking: ``CeleryBackend.revoke()`` calls ``current_app.control.revoke()`` to cancel the
  scheduled Celery task.

Available tasks (``djgentelella.async_notification.tasks``):

.. code:: python

    from djgentelella.async_notification.tasks import send_email_task, send_newsletter_task

    # Manually enqueue a notification
    send_email_task.delay(notification.pk)

    # Manually enqueue a newsletter task
    send_newsletter_task.delay(newsletter_task.pk)

----

Django Tasks Backend (Django 6+)
----------------------------------

Uses Django's built-in background task framework introduced in Django 6. No external broker is
required — tasks are stored in the database and processed by a dedicated worker process.

Requirements
^^^^^^^^^^^^^

- Django 6.0+ (provides ``django.tasks``).
- ``django-tasks`` database backend (``pip install django-tasks``), or another compatible
  ``django.tasks`` backend.
- A running ``manage.py db_worker`` process (for the database backend).

Installation
^^^^^^^^^^^^^

.. code:: bash

    pip install django-tasks

Settings
^^^^^^^^^

.. code:: python

    # settings.py

    INSTALLED_APPS = [
        ...,
        'django_tasks',              # Required for the database backend
        'django_tasks.backends.database',
        'djgentelella.async_notification',
    ]

    TASKS = {
        'default': {
            'BACKEND': 'django_tasks.backends.database.DatabaseBackend',
        }
    }

    # Optional: explicit backend (autodetect picks Django Tasks when TASKS is present)
    ASYNC_NOTIFICATION_BACKEND = 'djgentelella.async_notification.backends.django_tasks.DjangoTasksBackend'

Run the migration to create the task result table:

.. code:: bash

    python manage.py migrate

Starting the Worker
^^^^^^^^^^^^^^^^^^^^

.. code:: bash

    # Development / production
    python manage.py db_worker

How It Works
^^^^^^^^^^^^^

- Immediate send (``enqueued=False``): the ``post_save`` signal calls
  ``DjangoTasksBackend.send()``, which calls ``django_send_email_task.enqueue(notification_pk)``.
- Queued send (``enqueued=True``): the notification stays ``pending`` until the worker processes it
  or ``process_notifications`` is run.
- Newsletter scheduling: ``DjangoTasksBackend.schedule()`` calls
  ``django_send_newsletter_task.using(run_after=task.send_date).enqueue(newsletter_task_pk)``.
  The task ID is stored in ``NewsLetterTask.celery_task_id`` for later cancellation.
- Revoking: ``DjangoTasksBackend.revoke()`` calls ``DBTaskResult.cancel()`` on the stored task ID.

Available tasks (``djgentelella.async_notification.tasks``):

.. code:: python

    from djgentelella.async_notification.tasks import (
        django_send_email_task,
        django_send_newsletter_task,
    )

    # Manually enqueue a notification
    django_send_email_task.enqueue(notification.pk)

    # Manually schedule a newsletter for a future date
    from django.utils import timezone
    django_send_newsletter_task.using(
        run_after=timezone.now() + timezone.timedelta(hours=2)
    ).enqueue(newsletter_task.pk)

----

Comparison Summary
-------------------

.. list-table::
   :header-rows: 1
   :widths: 30 23 23 24

   * - Feature
     - Sync + cron
     - Celery
     - Django 6 Tasks
   * - External broker needed
     - No
     - Yes (Redis/RabbitMQ)
     - No
   * - Separate worker process
     - No (cron only)
     - Yes (``celery worker``)
     - Yes (``db_worker``)
   * - Scheduled sends (ETA)
     - Via cron polling
     - Native (``apply_async eta``)
     - Native (``run_after``)
   * - Task revocation
     - DB status only
     - Celery control API
     - ``DBTaskResult.cancel()``
   * - Additional packages
     - None
     - ``celery``
     - ``django-tasks``
   * - Recommended for
     - Dev / simple apps
     - Existing Celery stacks
     - New Django 6 projects

----

Custom Backends
----------------

You can implement your own backend by subclassing ``NotificationBackend``:

.. code:: python

    # myapp/notification_backend.py
    from djgentelella.async_notification.backends.base import NotificationBackend

    class MyCustomBackend(NotificationBackend):

        def send(self, notification_pk):
            """Dispatch a single EmailNotification."""
            # e.g. push to an SQS queue, call a webhook, etc.
            ...

        def schedule(self, newsletter_task_pk):
            """Schedule a NewsLetterTask for future sending."""
            ...

        def revoke(self, newsletter_task_pk):
            """Cancel a scheduled NewsLetterTask."""
            ...

Then point the setting to your class:

.. code:: python

    ASYNC_NOTIFICATION_BACKEND = 'myapp.notification_backend.MyCustomBackend'