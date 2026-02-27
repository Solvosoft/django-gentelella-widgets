Settings
===========================

All settings are optional and have sensible defaults. Configure them in your Django ``settings.py``.

Sending Backend
------------------

.. code:: python

    # Backend for sending notifications.
    # None = autodetect (Celery if available, otherwise sync)
    ASYNC_NOTIFICATION_BACKEND = None

When set to ``None``, the module will use Celery tasks if Celery is installed, otherwise it falls back to synchronous sending.

Batching & Retries
---------------------

.. code:: python

    # Maximum number of recipients per email batch (default: 40)
    ASYNC_NOTIFICATION_MAX_PER_MAIL = 40

    # Maximum number of retry attempts for failed sends (default: 3)
    ASYNC_NOTIFICATION_MAX_RETRIES = 3

When sending to many recipients, the module splits them into batches of ``ASYNC_NOTIFICATION_MAX_PER_MAIL``.
If a send fails, it retries up to ``ASYNC_NOTIFICATION_MAX_RETRIES`` times before marking the notification as ``failed``.

Default BCC/CC
-----------------

.. code:: python

    # Default BCC addresses added to every notification (comma-separated)
    ASYNC_BCC = None

    # Default CC addresses added to every notification (comma-separated)
    ASYNC_CC = None

These addresses are appended to every outgoing email in addition to the per-notification BCC/CC.

Email-Only Mode
------------------

.. code:: python

    # If set, only send email (skip DB notification creation)
    ASYNC_SEND_ONLY_EMAIL = None

SMTP Debug
--------------

.. code:: python

    # Enable SMTP debug output (default: False)
    ASYNC_SMTP_DEBUG = False

Base Templates
-----------------

.. code:: python

    # Base templates for email wrapping
    # Maps a key to a Django template path
    ASYNC_NOTIFICATION_BASE_TEMPLATES = {
        'default': 'myapp/email/base.html',
        'minimal': 'myapp/email/minimal.html',
    }

Base templates wrap the email content. The template receives the rendered content as the ``{{ content }}`` variable
plus all context variables. Example base template:

.. code:: html+django

    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif;">
        <div style="max-width: 600px; margin: 0 auto;">
            <header style="background: #333; color: #fff; padding: 20px;">
                <h1>My Company</h1>
            </header>
            <div style="padding: 20px;">
                {{ content|safe }}
            </div>
            <footer style="background: #f5f5f5; padding: 10px; text-align: center;">
                <small>&copy; 2026 My Company</small>
            </footer>
        </div>
    </body>
    </html>

Newsletter Configuration
---------------------------

.. code:: python

    # Custom SMTP server for newsletters
    ASYNC_NEWSLETTER_SEVER_CONFIGS = {
        'host': 'smtp.example.com',
        'port': 587,
        'username': 'newsletter@example.com',
        'password': 'secret',
        'use_tls': True,
    }

    # Model bases for newsletter templates
    # Maps a key to an 'app_label.ModelName' string
    ASYNC_NEWS_BASE_MODELS = {
        'users': 'auth.User',
        'customers': 'myapp.Customer',
    }

    # Newsletter header configuration
    ASYNC_NEWSLETTER_HEADER = {
        'logo': '/static/logo.png',
        'title': 'My Newsletter',
    }

Autocomplete Configuration
------------------------------

.. code:: python

    # User lookup fields for recipient autocomplete (default shown)
    ASYNC_NOTIFICATION_USER_LOOKUP_FIELDS = [
        'username', 'email', 'first_name', 'last_name'
    ]

    # Group lookup fields for autocomplete (default shown)
    ASYNC_NOTIFICATION_GROUP_LOOKUP_FIELDS = ['name']

Permission Classes
---------------------

.. code:: python

    # Custom permission classes for API views (list of dotted paths)
    # None = use default AuthAllPermBaseObjectManagement permissions
    ASYNC_NOTIFICATION_PERMISSION_CLASSES = None
