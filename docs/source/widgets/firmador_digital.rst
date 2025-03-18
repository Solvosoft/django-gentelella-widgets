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

DigitalSignatureFileAPIView Documentation
===========================================

Description
-----------
The ``DigitalSignatureFileAPIView`` is a Django REST Framework API view designed to serve PDF documents that are associated with digital signatures. This endpoint uses a custom renderer to output the PDF file content.

Renderer
--------
- **PDFRenderer**:
  This custom renderer class is responsible for rendering the PDF content correctly when a GET request is made to this API view.

HTTP Methods
------------
- **GET**:
  Retrieves the PDF file for a given digital signature.

  **URL Parameter**:
  - ``pk``: The primary key of the digital signature record.

  **Process**:
  1. Tries to retrieve a ``DigitalSignature`` instance from the database using the provided ``pk``.
  2. If the instance does not exist, returns a ``404 Not Found`` response with a message indicating that the file was not found.
  3. If the instance is found, the associated file is read in binary mode.
  4. The binary data is then returned with the content type set to ``application/pdf``.

Response Codes
--------------
- **200 OK**:
  The request was successful and the PDF file content is returned.
- **404 Not Found**:
  The digital signature with the specified primary key does not exist.

Example Implementation
----------------------
Below is the example implementation of the API view:

.. code-block:: python

    from rest_framework.views import APIView
    from rest_framework.response import Response
    from rest_framework import status

    from demoapp.models import DigitalSignature
    from djgentelella.firmador_digital.consumers.pdf_render import PDFRenderer


    class DigitalSignatureFileAPIView(APIView):
        renderer_classes = [PDFRenderer]

        def get(self, request, pk, format=None):
            try:
                signature = DigitalSignature.objects.get(pk=pk)
            except DigitalSignature.DoesNotExist:
                return Response({"detail": "File not found"}, status=status.HTTP_404_NOT_FOUND)

            file_path = signature.file.path
            with open(file_path, 'rb') as f:
                file_data = f.read()

            return Response(file_data, content_type='application/pdf')

Digital Signature View Documentation
======================================

Description
-----------
The ``digital_signature_view`` is a Django view that renders the digital signature interface. It is responsible for providing the digital signature form to the associated template, enabling users to interact with the digital signature process.

Template Rendering
------------------
- **Template Path**:
  The view renders the template located at ``gentelella/digital_signature/digital_signature.html``. This template is designed to display the digital signature form and related elements.

Context Variables
-----------------
- **form**:
  The context dictionary includes an instance of ``DigitalSignatureForm``.
  - The form is instantiated with the prefix ``"update"`` to ensure unique field naming, particularly useful if multiple forms are present on the same page.

Usage
-----
This view is typically connected to a URL in the Django project's URL configuration, making the digital signature interface accessible to users.

Example Implementation
----------------------
.. code-block:: python

    from django.shortcuts import render
    from .forms import DigitalSignatureForm

    def digital_signature_view(request):
        return render(
            request,
            'gentelella/digital_signature/digital_signature.html',
            context={
                'form': DigitalSignatureForm(prefix='update'),
            }
        )

DigitalSignature Model Documentation
======================================

Description
-----------
The ``DigitalSignature`` model is designed to manage digital signature files within the application. It encapsulates the core fields required for handling documents that need to be digitally signed. The three fundamental fields are:

- **file**: Contains the actual document to be signed.
- **filename**: Stores the name of the file.
- **pk**: An auto-generated primary key provided by Django.

In addition, the model includes extra fields to enhance traceability and uniqueness.

Model Fields
------------
- **pk**:
  The auto-generated primary key of the model, created by Django.

- **file_code**:
  A unique UUID field used to uniquely identify each digital signature entry. It is generated by ``uuid.uuid4`` and is not editable.

- **filename**:
  A character field (maximum length of 50) that holds the name of the file. This field is optional (can be null or blank) and is automatically populated from the file name if not provided.

- **file**:
  A file field that stores the digital signature document. Files are uploaded to the ``digital_signature/`` directory.

- **created**:
  A timestamp set automatically when the record is first created.

- **updated**:
  A timestamp updated automatically whenever the record is saved.

Custom Methods
--------------
- **save()**:
  Overrides the default save method to populate the ``filename`` field automatically using the uploaded file's name (if the filename is not already set). After this customization, it calls the parent class's save method.

- **__str__()**:
  Returns the ``filename`` if available; otherwise, it returns the string representation of the ``file_code``.

Example Implementation
----------------------
.. code-block:: python

    class DigitalSignature(models.Model):
        file_code = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
        filename = models.CharField(max_length=50, null=True, blank=True)
        file = models.FileField(upload_to='digital_signature/')
        created = models.DateTimeField(auto_now_add=True)
        updated = models.DateTimeField(auto_now=True)

        def save(self, *args, **kwargs):
            # Add name to filename if not provided
            if not self.filename and self.file:
                self.filename = self.file.name.split('/')[-1]
            super().save(*args, **kwargs)

        def __str__(self):
            return self.filename or str(self.file_code)


Digital Signature Template Documentation
==========================================

Overview
--------
This template renders the digital signature interface within the Django application. It extends the base site template and loads the required tags for configuration and static file management. The template displays a digital signature form and defines essential JavaScript variables that control the signature process.

Template Structure
------------------
- **Extends**:
  The template extends ``gentelella/base_site.html`` to inherit the site's layout and styles.

- **Template Tags**:
  It load ``static`` for handling static files.

- **Content Block**:
  The main content is wrapped in a card layout. Inside this layout, a digital signature form is rendered, complete with CSRF protection. The form is submitted (via a hidden submit button) to process the digital signature.

Key JavaScript Variables
------------------------
Within the ``js`` block, two important variables are defined:

1. **urls**
   - **sign_doc**:
     The URL to the document that needs to be signed. This URL is obtained from the API endpoint created to serve the document.
   - **logo**:
     The URL for the logo image, loaded from the static files. This image is displayed in the PIN entry window of the digital signature interface. This variable is optional and can be omitted if no logo is required.

2. **doc_instance**
   - **pk**:
     The primary key of the digital signature document.
   - **model**:
     The name of the model managing the document files, in this case, ``DigitalSignature``.
   - **app**:
     The name of the Django app (``demoapp``) where the model is defined.

Example Template Implementation
-------------------------------
.. code-block:: html

    {% extends 'gentelella/base_site.html' %}
    {% load static %}

    {% block content %}
        {# Container #}
        <div class="row">
            <div class='col-12'>
                <div class="card">
                    <div class="card-body">
                        {# Title page #}
                        <div class="card-title titles">
                            <h1 class="text-center"> Digital Signature </h1>
                        </div>
                        {# Main content #}
                        <main>
                            {# Form #}
                            <div class="my-3">
                                <form action="" method="POST">
                                    {% csrf_token %}
                                    {# Widget #}
                                    {{ form }}
                                    <input type="submit" id="hidden-submit" style="display: none;">
                                </form>
                            </div>
                        </main>
                    </div>
                </div>
            </div>
        </div>
    {% endblock %}

    {% block js %}
        <script>
            const urls = {
                // File to sign: URL obtained from the API that serves the document.
                sign_doc: "{% url 'digital_signature_file_api' pk=2 %}",
                // Logo: URL in static files for the image displayed in the PIN entry window.
                logo: "{% static 'gentelella/images/firmador.ico' %}",
            }
            const doc_instance = {
                // Primary key of the document.
                "pk": 2,
                // Model name used to manage the document files.
                "model": "DigitalSignature",
                // Django app where the model is defined.
                "app": "demoapp",
            }
        </script>
    {% endblock %}

Conclusion
----------
This template integrates both the visual interface for initiating a digital signature process and the necessary JavaScript configuration. The variables defined in the ``urls`` and ``doc_instance`` objects are essential as they establish the API endpoint for retrieving the document and identify the document instance within the application.

Extras for Widget Functionality
================================

User Signature Configuration
----------------------------
To fully enable the digital signature widget, additional configuration per user is required.

- **UserSignatureConfig Record**:
      - Access the Django admin interface and create a record of type ``UserSignatureConfig``.
      - Associate the configuration record with the appropriate user.
      - This record stores user-specific settings necessary for the proper functioning of the digital signature widget.
      - Optionally, implement a CRUD interface to manage these configurations within the application.

Document Record Management
--------------------------
A corresponding document record must be created that links a file with its primary key.

- **Document Record**:
      - The record should include the file to be signed and its auto-generated primary key (``pk``).
      - This record can be created through the Django admin or via a custom CRUD interface.
      - The information stored in this record is used by the widget to locate and process the correct document.


Widget Configuration Integration
----------------------------------
The following JavaScript variables are critical for the widget's operation:

- **doc_instance**:

  .. code-block:: javascript

      const doc_instance = {
          // Primary key of the document.
          "pk": 2,
         ...
      }

- **urls**:

  .. code-block:: javascript

      const urls = {
          // File to sign: URL obtained from the API that serves the document.
          sign_doc: "{% url 'digital_signature_file_api' pk=2 %}",
          ...
      }

Summary
-------
To ensure proper functionality of the digital signature widget:

- Create and manage a ``UserSignatureConfig`` record via the admin or a custom CRUD interface to store user-specific settings.
- Ensure a document record exists that associates the file with its primary key (``pk``), also manageable via the admin or a CRUD interface.
- Integrate these settings into the widget using the ``doc_instance`` and ``urls`` variables, which provide the necessary API endpoint and static asset references.

