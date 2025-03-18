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
        # websocket
        DJANGO_ASETTINGS_MODULE = "demo.asettings"
        GUNICORN_BIND = "127.0.0.1:9022" if DEBUG else "unix:/run/supervisor/gunicorn_asgi.sock"
        GUNICORN_ASGI_APP = "demo.asgi:application"
        GUNICORN_WSGI_APP = "demo.wsgi:application"
        GUNICORN_WORKERS = 1 if DEBUG else 2
        GUNICORN_WORKER_CLASS = "demo.asgi_worker.UvicornWorker"
        GUNICORN_USER = "demo"
        GUNICORN_GROUP = "demo"

        # firmador libre
        FIRMADOR_CORS = "http://127.0.0.1:8000"
        FIRMADOR_WS = "ws://127.0.0.1:9022/async/"
        FIRMADOR_WS_URL = FIRMADOR_WS + "sign_document"
        FIRMADOR_DOMAIN = "http://localhost:9001"
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





Widget Variables
----------------
- **ws_url**:
  The URL of the WebSocket that connects to the digital signing service.

- **cors**:
  The URL and port where the application is running, which communicates with the signing service. This setting configures the necessary CORS permissions.

- **title**:
  An optional title displayed in the widget's HTML interface, allowing customization of the widget's presentation.

- **default_page**:
  Specifies the default page to load when displaying the document. Accepted values include:

  - ``"last"``: Loads the last page of the document.
  - ``"first"``: Loads the first page of the document.
  - A numeric value: Loads the page corresponding to the given number.

Example Implementation in a Form
--------------------------------

Below is an example of how the ``DigitalSignatureForm`` is implemented:

.. code-block:: python

    class DigitalSignatureForm(GTForm, forms.ModelForm):

        class Meta:
            model = DigitalSignature
            fields = ['file']
            widgets = {
                'file': DigitalSignatureInput(
                    ws_url="%s" % settings.FIRMADOR_WS_URL,
                    cors="%s" % settings.FIRMADOR_CORS,
                    title=_("Widget Digital Signature"),
                    default_page="last"
                )
            }
