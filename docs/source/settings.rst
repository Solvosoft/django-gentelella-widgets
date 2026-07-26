Settings
==========================

Settings on settings.py
--------------------------
This apps are required for correct working of Djgentelella

.. code:: python

    INSTALLED_APPS = [
        ...,
        'djgentelella',
        'rest_framework',
    ]

``djgentelella.blog`` and ``djgentelella.permission_management`` are optional;
add them only if you use those apps. (``demoapp`` belongs to this repository's
demo project, not to an installation of the library.)

Follow settings are required

.. code:: python

    JQUERY_URL = None

Follow settings are recommended

.. code:: python

    STATIC_URL = os.getenv('STATIC_URL', '/static/')
    STATIC_ROOT = os.path.join(BASE_DIR, 'static/')
    MEDIA_URL = os.getenv('MEDIA_URL', '/media/')
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')
    TINYMCE_UPLOAD_PATH = os.path.join(MEDIA_ROOT, 'tinymce')

Optional  You can define a default import of some JS an CSS, see section "Using in templates" for more.

.. code:: python

    DEFAULT_JS_IMPORTS = {
        'use_readonlywidgets': True,
        'use_flags': True
    }



Settings of the optional modules
---------------------------------

These only matter if you use the module they belong to; each page documents them
in full.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Module
     - Settings
   * - Voice dictation (:doc:`widgets/voice`)
     - ``GENTELELLA_ASR_BACKEND``, ``GENTELELLA_ASR_REMOTE_URL``,
       ``GENTELELLA_ASR_REMOTE_TOKEN``, ``GENTELELLA_ASR_TIMEOUT``,
       ``GENTELELLA_ASR_MAX_UPLOAD_BYTES``, ``GENTELELLA_ASR_REMOTE_MODEL``,
       ``GENTELELLA_ASR_REMOTE_PROMPT_PARAM``,
       ``GENTELELLA_ASR_REMOTE_HOTWORDS_PARAM``, ``GENTELELLA_ASR_MODEL``,
       ``GENTELELLA_ASR_QUANTIZATION``, ``GENTELELLA_ASR_LANGUAGE``,
       ``GENTELELLA_ASR_PNC``
   * - Async notifications (:doc:`async_notification/installation`)
     - ``ASYNC_NOTIFICATION_BACKEND``, ``CELERY_BROKER_URL``
   * - Chunked uploads
     - ``TINYMCE_UPLOAD_PATH`` (above), plus the ``chunked_upload`` settings

Settings on Database
---------------------------

You can configurate some settings on database using django admin views `/admin/djgentelella/gentelellasettings/`

- **use_compress_static:** Compress Css and Js to provide less file including several files on one file.
- **site_theme:** Path for your theme css, with this you can change the appearance of your site.
- **site_logo:** Change logo display on footer.
- **site_title:** Change the default title of pages.


