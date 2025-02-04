Digital Signature
=================

This component allows us to digitally sign documents, and the interface to perform this process.

It is important to highlight that for this process we will use **'Firmador Libre'**, which is an application that facilitates the signing of documents.

Configurations
--------------

This process is done through a socket, which communicates with an API, free signer, and our project. So we will configure our project to carry out this process.

1. Configurations in settings.py
---------------------------------

Djgentelella already implements the required libraries for the following configurations:

    a) Add to ``INSTALLED_APPS``::

           INSTALLED_APPS = [
               # others apps
               "corsheaders",
               # ...
           ]

    b) Add the ``MIDDLEWARE``::

           MIDDLEWARE = [
               "corsheaders.middleware.CorsMiddleware",
               "django.middleware.security.SecurityMiddleware",
               # others middlewares...
           ]

    c) Add the ``CORS_ALLOW_ALL_ORIGINS``::

            CORS_ALLOW_ALL_ORIGINS = True

     or::

           CORS_ALLOWED_ORIGINS = [
               "http://localhost:3000",
               "https://tudominio.com",
           ]

    d) Add channels in ``INSTALLED_APPS``::

           INSTALLED_APPS = [
               # others apps
               "channels",
               # ...
           ]

    e) Add variables in ``settings.py``::

        # change the value demo for your project in all variables
        DJANGO_ASETTINGS_MODULE = "demo.asettings"
        GUNICORN_BIND = "localhost:9022" if DEBUG else "unix:/run/supervisor/gunicorn_asgi.sock"
        GUNICORN_ASGI_APP = "demo.asgi:application"
        GUNICORN_WSGI_APP = "demo.wsgi:application"
        GUNICORN_WORKERS = 1 if DEBUG else 2
        GUNICORN_WORKER_CLASS = "demo.asgi_worker.UvicornWorker"
        GUNICORN_USER = "demo"
        GUNICORN_GROUP = "demo"

        FIRMADOR_WS = os.getenv("FIRMADOR_WS", "ws://127.0.0.1:9022/async/")
        FIRMADOR_DOMAIN = os.getenv("FIRMADOR_DOMAIN", "http://localhost:9001")
        FIRMADOR_VALIDA_URL = FIRMADOR_DOMAIN + "/valida/"
        FIRMADOR_SIGN_URL = FIRMADOR_DOMAIN + "/firma/firme"
        FIRMADOR_SIGN_COMPLETE = FIRMADOR_DOMAIN + "/firma/completa"
        FIRMADOR_DELETE_FILE_URL = FIRMADOR_DOMAIN + "/firma/delete"


2. Add files for asgi configuration
-----------------------------------

    a) Update a file ``asgi.py`` in main app::

        from djgentelella.firmador_digital.config.asgi_config import AsgiConfig
        application = AsgiConfig("demo.settings").application

    b) Create a file ``asgi_worker.py`` in main app::

        from uvicorn_worker import UvicornWorker as BaseUvicornWorker

        class UvicornWorker(BaseUvicornWorker):
            CONFIG_KWARGS = {"lifespan": "off", "loop": "auto", "http": "auto"}

    c) Create a file ``auls.py`` in main app::

        urlpatterns = []

    d) Create a file ``asettings.py`` in main app::

        from .settings import *

        ROOT_URLCONF = "my_main_app.aurls"


