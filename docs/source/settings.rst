Settings
==========================

Settings on settings.py
--------------------------
This apps are required for correct working of Djgentelella

.. code:: python

    INSTALLED_APPS = [
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        ...,
        'djgentelella',
        'rest_framework',
    ]

``django.contrib.admin`` is not optional: the change tracking in
``djgentelella.history`` records through ``django.contrib.admin.models.LogEntry``
and ``djgentelella/models.py`` imports it at module level, so leaving it out
fails at startup with ``Model class django.contrib.admin.models.LogEntry
doesn't declare an explicit app_label``.

``djgentelella.blog`` and ``djgentelella.async_notification`` are optional; add
them only if you use them. They are the only subpackages that are Django apps in
their own right — ``permission_management``, ``notification``,
``chunked_upload``, ``trash``, ``history``, ``voice`` and ``firmador_digital``
are plain Python modules reached through ``djgentelella.urls``, and listing them
in ``INSTALLED_APPS`` has no effect. (``demoapp`` belongs to this repository's
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
    }



Optional, the menu widgets the project declares besides the registered ones
(see :doc:`menus`, "Custom Widgets"); a widget item that names any other class
is not drawn:

.. code:: python

    GT_MENU_WIDGETS = ['myapp.widgets.ClockMenu']

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
   * - Encrypted model fields (:doc:`model_fields`)
     - ``GT_ENCRYPTION_KEY``
   * - Theme roller (:doc:`theme`)
     - ``GT_THEME_LOGO_MAX_BYTES``
   * - User feedback (:doc:`feedback`)
     - ``GT_FEEDBACK``; per Site, the database setting ``feedback_enabled``

Settings on Database
---------------------------

You can configurate some settings on database using django admin views `/admin/djgentelella/gentelellasettings/`

- **use_compress_static:** Compress Css and Js to provide less file including several files on one file.
- **site_theme:** Path for your theme css, with this you can change the appearance of your site.
- **site_logo:** Change logo display on footer.
- **site_title:** Change the default title of pages.

Each of them can also be set for one ``Site`` only, which then wins over the
global value on that site: ``set_settings(key, value, site=site)`` or the
*Site* field in the admin. See :doc:`sites`.

The migrations of djgentelella create the four global values
(``djgentelella.utils.DEFAULT_SETTINGS``). Whatever empties the database
after them -- the *flush* of a ``TransactionTestCase`` or of a live server
(Selenium) test -- leaves none, and the pages lose their title, theme and
bundled static files. ``load_default_settings()`` creates the missing ones
again; call it in the ``setUp`` of such a test. ``overwrite=True`` resets the
existing ones too, and keyword arguments replace or add values
(``use_compress_static=None`` leaves that key out). A page without
``site_theme`` loads ``gentelella/css/custom.css``.

.. code:: python

    from djgentelella.utils import load_default_settings

    class MyBrowserTest(StaticLiveServerTestCase):
        def setUp(self):
            load_default_settings()

Which values are HTML
^^^^^^^^^^^^^^^^^^^^^

``{% get_settings 'key' %}`` prints a value **escaped**, as text, unless its
key is one of the HTML settings: only ``site_logo`` by default. Store plain
text in ``site_title``, ``sidebar_title``, ``sidebar_icon`` and the rest; a
value with markup shows the markup as text. A character reference is kept as
it is (``Sales &lt;North&gt;`` shows ``Sales <North>``, not ``&amp;lt;``), so
values that were stored escaped by hand while the tag printed everything
unescaped keep showing the same text.

``settings.GT_HTML_SETTINGS`` replaces the list of HTML keys:

.. code:: python

    GT_HTML_SETTINGS = ['site_logo', 'footer_html']

An HTML setting is printed as it is: only trusted staff may edit it (the
admin of ``GentelellaSettings``). In Python, ``djgentelella.utils``
offers ``get_settings_display(key, site=None, default='')`` (what the tag
prints, already safe), ``setting_allows_html(key)``, ``html_settings()`` and
``escape_setting(value)``; ``get_settings(key, site)`` still returns the
stored value as it is.


