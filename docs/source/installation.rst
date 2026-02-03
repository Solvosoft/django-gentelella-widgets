Installation
=============

This guide covers installing Django Gentelella Widgets and configuring your project.

Requirements
--------------

- Python 3.11 or higher
- Django 4.2 or higher
- Django REST Framework

Basic Installation
--------------------

Install from PyPI:

.. code:: bash

    pip install djgentelella

Configuration
---------------

1. Add Required Apps
""""""""""""""""""""""

Add the following to your ``INSTALLED_APPS`` in ``settings.py``:

.. code:: python

    INSTALLED_APPS = [
        # Django apps...
        'django.contrib.staticfiles',

        # Required apps
        'djgentelella',
        'rest_framework',
        'markitup',

        # Optional apps (add as needed)
        'djgentelella.blog',
        'djgentelella.permission_management',
        'djgentelella.notification',
        'djgentelella.chunked_upload',

        # Your apps...
    ]

2. Required Settings
""""""""""""""""""""""

Add these required settings:

.. code:: python

    # Markitup configuration (for WYSIWYG editor)
    MARKITUP_FILTER = ('markdown.markdown', {'safe_mode': True})
    MARKITUP_SET = 'markitup/sets/markdown/'
    JQUERY_URL = None

3. Recommended Settings
"""""""""""""""""""""""""

.. code:: python

    import os
    from pathlib import Path

    BASE_DIR = Path(__file__).resolve().parent.parent

    # Static and media files
    STATIC_URL = '/static/'
    STATIC_ROOT = os.path.join(BASE_DIR, 'static/')
    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')

    # TinyMCE upload path
    TINYMCE_UPLOAD_PATH = os.path.join(MEDIA_ROOT, 'tinymce')

4. URL Configuration
""""""""""""""""""""""

Include djgentelella URLs in your ``urls.py``:

.. code:: python

    from django.urls import path, include
    from djgentelella.urls import urlpatterns as djgentelella_urls

    urlpatterns = [
        # Your URLs...
        path('', include(djgentelella_urls)),
    ]

5. Run Migrations
"""""""""""""""""""

.. code:: bash

    python manage.py migrate

6. Load Static Files
""""""""""""""""""""""

Download and set up frontend assets:

.. code:: bash

    pip install requests
    python manage.py loaddevstatic

7. Generate Base JavaScript
"""""""""""""""""""""""""""""

Generate the base JavaScript file for widgets:

.. code:: bash

    python manage.py createbasejs


Optional Features
-------------------

Chunked File Upload
"""""""""""""""""""""

For large file uploads with progress tracking:

1. Add to ``INSTALLED_APPS``:

.. code:: python

    INSTALLED_APPS = [
        # ...
        'djgentelella.chunked_upload',
    ]

2. Run migrations:

.. code:: bash

    python manage.py migrate

3. Configure cleanup (optional):

.. code:: bash

    # Delete expired uploads (run periodically via cron)
    python manage.py delete_expired_uploads

Digital Signature Integration
"""""""""""""""""""""""""""""""

For digital document signing with Firmador Libre:

1. Install additional dependencies:

.. code:: bash

    pip install channels uvicorn

2. Add to ``INSTALLED_APPS``:

.. code:: python

    INSTALLED_APPS = [
        # ...
        'corsheaders',
        'channels',
    ]

3. Add CORS middleware (must be first):

.. code:: python

    MIDDLEWARE = [
        'corsheaders.middleware.CorsMiddleware',
        'django.middleware.security.SecurityMiddleware',
        # other middleware...
    ]

4. Configure CORS:

.. code:: python

    CORS_ALLOW_ALL_ORIGINS = True
    # Or for production:
    # CORS_ALLOWED_ORIGINS = [
    #     "https://yourdomain.com",
    # ]

5. Add WebSocket and Firmador settings:

.. code:: python

    # WebSocket configuration
    DJANGO_ASETTINGS_MODULE = "yourproject.asettings"
    GUNICORN_BIND = "127.0.0.1:9022"
    GUNICORN_ASGI_APP = "yourproject.asgi:application"
    GUNICORN_WSGI_APP = "yourproject.wsgi:application"
    GUNICORN_WORKERS = 2
    GUNICORN_WORKER_CLASS = "yourproject.asgi_worker.UvicornWorker"

    # Firmador Libre configuration
    FIRMADOR_CORS = "http://127.0.0.1:8000"
    FIRMADOR_WS = "ws://127.0.0.1:9022/async/"
    FIRMADOR_WS_URL = FIRMADOR_WS + "sign_document"
    FIRMADOR_DOMAIN = "http://localhost:9001"
    FIRMADOR_VALIDA_URL = FIRMADOR_DOMAIN + "/valida/"
    FIRMADOR_SIGN_URL = FIRMADOR_DOMAIN + "/firma/firme"
    FIRMADOR_SIGN_COMPLETE = FIRMADOR_DOMAIN + "/firma/completa"
    FIRMADOR_DELETE_FILE_URL = FIRMADOR_DOMAIN + "/firma/delete"

6. Create ASGI configuration files:

**asgi.py:**

.. code:: python

    from djgentelella.firmador_digital.config.asgi_config import AsgiConfig
    application = AsgiConfig("yourproject.settings").application

**asgi_worker.py:**

.. code:: python

    from uvicorn_worker import UvicornWorker as BaseUvicornWorker

    class UvicornWorker(BaseUvicornWorker):
        CONFIG_KWARGS = {"lifespan": "off", "loop": "auto", "http": "auto"}

**aurls.py:**

.. code:: python

    urlpatterns = []

**asettings.py:**

.. code:: python

    from .settings import *
    ROOT_URLCONF = "yourproject.aurls"

See the :doc:`widgets/advancedwidgets` section for detailed Digital Signature widget documentation.

Notification System
"""""""""""""""""""""

For user notifications:

1. Add to ``INSTALLED_APPS``:

.. code:: python

    INSTALLED_APPS = [
        # ...
        'djgentelella.notification',
    ]

2. Run migrations:

.. code:: bash

    python manage.py migrate

History/Audit Trail
"""""""""""""""""""""

For tracking model changes:

1. Add to ``INSTALLED_APPS``:

.. code:: python

    INSTALLED_APPS = [
        # ...
        'djgentelella.history',
    ]

2. Run migrations:

.. code:: bash

    python manage.py migrate


Default JavaScript Imports
----------------------------

You can configure default JavaScript imports in settings:

.. code:: python

    DEFAULT_JS_IMPORTS = {
        'use_readonlywidgets': True,
        'use_flags': True
    }


Verification
--------------

To verify your installation, run the development server:

.. code:: bash

    python manage.py runserver

Then visit ``http://localhost:8000/`` and check that:

1. Static files are loading (Bootstrap styles applied)
2. JavaScript widgets are functional
3. No console errors in browser developer tools

