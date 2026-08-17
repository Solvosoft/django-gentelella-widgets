Management Commands
===========================

The module provides three management commands for processing, inspection, and demo data generation.

process_notifications
------------------------

Processes pending email notifications and due newsletter tasks. Designed for cron-based deployments
without Celery.

.. code:: bash

    python manage.py process_notifications

**What it does:**

1. Finds all ``EmailNotification`` objects with ``status='pending'`` and ``enqueued=True``.
2. Locks each one (using ``select_for_update(skip_locked=True)``), sets status to ``sending``, and sends it.
3. Finds all ``NewsLetterTask`` objects with ``status`` in ``('pending', 'scheduled')`` and ``send_date`` in the past.
4. Locks each one, sets status to ``sending``, and sends the associated newsletter.
5. Cleans up orphaned ``AttachedFile`` objects (``object_id=0``, older than 24 hours) and deletes their files.
6. Reports the number of sent, failed, and cleaned items.

**Cron example:**

.. code:: bash

    # Run every 5 minutes
    */5 * * * * cd /path/to/project && python manage.py process_notifications

.. note::

    The command uses ``select_for_update(skip_locked=True)`` for safe concurrent execution.
    Multiple instances can run simultaneously without processing the same notification twice.

inspect_notification
-----------------------

Displays the current async_notification system configuration: settings, registered contexts,
model fields, and resolvers.

.. code:: bash

    # Show all configuration
    python manage.py inspect_notification

    # Show detailed model fields for each context
    python manage.py inspect_notification --fields

    # Filter by a specific context code
    python manage.py inspect_notification --context order_confirmation --fields

    # Output in JSON format (for scripting)
    python manage.py inspect_notification --json

**Arguments:**

- ``--context CODE`` - Filter output to a specific context code.
- ``--fields`` - Show detailed model fields for each registered context.
- ``--json`` - Output in JSON format instead of human-readable text.

**Example output:**

.. code:: text

    === Settings ===
      ASYNC_NOTIFICATION_BACKEND: None
      ASYNC_NOTIFICATION_MAX_PER_MAIL: 40
      ASYNC_NOTIFICATION_MAX_RETRIES: 3
      ...

    === Registered Contexts ===
      [order_confirmation]
        Subject: Order #{{ order.id }} Confirmed
        Models: {'order': 'myapp.Order', 'user': 'auth.User'}
        Extra Variables: {'site_url': 'Full URL of the site'}
        Depth: 2
        Fields:
          {{ order.id }} [integer] ID
          {{ order.total }} [decimal] Total
          {{ user.username }} [string] Username
          {{ user.email }} [email] Email address
          {{ site_url }} (custom) - Full URL of the site

    === Resolvers ===
      @group.local -> DjangoGroupResolver

create_notification_demo
---------------------------

Generates demo data for all async_notification models. Useful for development and testing.

.. code:: bash

    # Create demo data
    python manage.py create_notification_demo

    # Clear existing data first
    python manage.py create_notification_demo --clear

    # Associate with a specific user
    python manage.py create_notification_demo --clear --user admin

**Arguments:**

- ``--clear`` - Delete all existing async_notification data before creating demo data.
- ``--user USERNAME`` - Username to associate with notifications and newsletters.

**Created data:**

- **3 Email Templates:** ``welcome``, ``password-reset``, ``order-confirmation``
- **4 Email Notifications:** One for each status (``pending``, ``sending``, ``sent``, ``failed``)
- **2 Newsletter Templates:** ``monthly-digest``, ``product-announcement``
- **2 Newsletters:** One per template with sample recipients
- **8 Newsletter Tasks:** 4 statuses per newsletter (``pending``, ``scheduled``, ``sent``, ``failed``)

.. note::

    The ``createdemo`` command in the demo app automatically calls ``create_notification_demo --clear``
    as part of the full demo data setup.
