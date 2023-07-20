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
        'demoapp',
        'djgentelella.blog',
        'djgentelella.permission_management',
        'markitup',
    ]

Follow settings are required

.. code:: python

    MARKITUP_FILTER = ('markdown.markdown', {'safe_mode': True})
    MARKITUP_SET = 'markitup/sets/markdown/'
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



Settings on Database
---------------------------

You can configurate some settings on database using django admin views `/admin/djgentelella/gentelellasettings/`

- **use_compress_static:** Compress Css and Js to provide less file including several files on one file.
- **site_theme:** Path for your theme css, with this you can change the appearance of your site.
- **site_logo:** Change logo display on footer.
- **site_title:** Change the default title of pages.


