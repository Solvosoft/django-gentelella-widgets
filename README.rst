Django Gentelella Widgets
############################

.. image:: https://img.shields.io/pypi/v/djgentelella?logo=pypi&logoColor=white
  :alt: Gentelella on PyPI
  :target: https://pypi.org/project/djgentelella/

.. image:: https://img.shields.io/readthedocs/django-gentelella-widgets?label=Read%20the%20Docs&logo=read%20the%20docs&logoColor=white
  :alt: Gentelella documentation

.. image:: https://img.shields.io/pypi/pyversions/djgentelella
  :alt: Gentelella supported python versions

.. image:: https://github.com/Solvosoft/django-gentelella-widgets/actions/workflows/django.yml/badge.svg
  :alt: Gentelella test status

.. image:: docs/source/_static/readme/logo.png
  :width: 200
  :alt: Gentelella Logo
  :align: right

Build beautiful Django applications faster with **djgentelella** — a comprehensive widget and utility library that seamlessly integrates Bootstrap 5 with popular JavaScript libraries into Django's form system.

Stop writing repetitive frontend code. Django Gentelella Widgets provides 40+ production-ready form widgets, a complete CRUD system with permissions, and enterprise features like transactional email, soft-delete, audit logging and chunked file uploads — all styled with the elegant `Gentelella <https://colorlib.com/polygon/gentelella/index.html>`_ admin theme.

Requirements
______________

- **Python** 3.11 or higher
- **Django** 5.2 or higher — both 5.2 (the current LTS) and 6.0 are exercised in CI
- **Django REST Framework** 3.15.2 or higher

``django.contrib.admin`` must be in ``INSTALLED_APPS``: change tracking records
through its ``LogEntry`` model.

Why Django Gentelella Widgets?
________________________________

**For Developers Who Value Their Time**

- **Drop-in widgets** — Replace Django's basic form widgets with rich, interactive components. Select2 autocomplete, date range pickers, WYSIWYG editors, and more work out of the box.
- **Multiple form layouts** — Render forms as horizontal, inline, grid, or plain layouts with a single method call (``form.as_horizontal()``, ``form.as_grid()``).
- **Complete CRUD views** — Build admin interfaces in minutes with permission-aware list, create, update, and delete views.

**For Applications That Need to Scale**

- **Transactional email & newsletters** — Template-driven sending with recipient resolvers, batching, retries and scheduled newsletters. Dispatch runs in-process by default and moves to a Celery queue by installing one extra.
- **Soft delete & trash** — Never lose data accidentally. Deleted records go to trash and can be restored.
- **Audit trail** — Track every change with automatic history logging including who changed what and when.
- **Chunked file uploads** — Handle large files reliably with resumable uploads and progress tracking.
- **Field-level encryption** — Protect sensitive data with AES encryption at the database level.

**For Teams Building Modern Web Apps**

- **REST API ready** — Built-in Django REST Framework serializers for notifications, history, and trash.
- **Real-time notifications** — User notification system with WebSocket support via Django Channels.
- **Voice dictation** — Speak into a textarea or a TinyMCE editor, transcribed in-process or by an external ASR service.
- **Digital signatures** — Integrate document signing workflows into your application.
- **Permission management** — Organize and assign permissions by category with a visual interface.

Key Features
______________

**Form Widgets**

- Text inputs with masks (email, phone, credit card, tax ID)
- Date/time pickers with range selection
- Select2-powered dropdowns with autocomplete and remote data
- Tree selectors for hierarchical data, built on ``django-tree-queries``
- File uploads with chunking and media recording (image, video, audio)
- WYSIWYG and TinyMCE rich text editors
- Voice dictation (``VoiceDictation``, ``VoiceEditorTinymce``) with live speech-to-text
- Interactive components: calendars, timelines, story maps, charts
- Digital signature capture

**Application Components**

- **CRUD System** — Generic permission-aware views with filtering, pagination, and search
- **Object Management** — Datatable and modal driven CRUD over a REST API, including objects scoped to a parent instance
- **Async Notification** — Email templates with live preview, newsletters, recipient resolvers, suppression lists and one-click unsubscribe (RFC 8058)
- **Notification System** — Categorized user notifications with REST API
- **Trash System** — Soft delete with restore capability
- **History System** — Automatic audit logging of all changes
- **Permission Management** — Visual permission assignment by group and user
- **Menu System** — Dynamic, permission-aware navigation menus
- **Blog Module** — Full-featured blog with categories and SEO sitemaps

**Frontend Libraries Included**

Bootstrap 5, Select2, DataTables, Chart.js, FullCalendar, DateRangePicker, HTMX, SweetAlert2, TinyMCE, and more — all bundled and ready to use

Documentation
________________

See `Documentation <https://django-gentelella-widgets.readthedocs.io/>`_

Installation
________________

Installing from pypi


.. code:: bash

   pip install djgentelella


Optional extras
------------------

None of these are needed to install or import ``djgentelella``; add only the
one you use.

.. code:: bash

    pip install "djgentelella[firmador]"     # digital signature over websockets
    pip install "djgentelella[celery]"       # queue-backed async_notification dispatch
    pip install "djgentelella[asr]"          # voice dictation transcribed in-process
    pip install "djgentelella[asr-remote]"   # voice dictation transcribed elsewhere
    pip install "djgentelella[dev]"          # asset bundling and minification (pylp)

The two ``asr`` extras back the voice dictation widgets and you need at most
one of them: ``asr`` runs Parakeet-v3 inside the Django process (the first
request downloads a ~670 MB model), ``asr-remote`` forwards the audio to an
external ASR API. Without the matching extra the transcription endpoint answers
``501`` naming the one to install.

``celery`` is autodetected: with Celery installed **and** ``CELERY_BROKER_URL``
set, notifications go through the queue; otherwise they are sent in-process by
``SyncBackend``, with nothing to configure.

Configure your settings

.. code:: bash

    INSTALLED_APPS = [ ..
        'django.contrib.admin',
        'djgentelella',
        'rest_framework',

        # optional, add as needed
        'djgentelella.blog',
        'djgentelella.permission_management',
        'djgentelella.async_notification',
    ]
    JQUERY_URL = None

``django.contrib.admin`` is required: change tracking records through its
``LogEntry`` model.



Run migrations

.. code:: bash

    python manage.py migrate

Create statics files downloading from internet (you need to install requests for this step).

.. code:: bash

     pip install requests
     python manage.py loaddevstatic

Add djgentelella urls in your project urls.py file

.. code:: bash

    from djgentelella.urls import urlpatterns as djgentelellaurls

    urlpatterns = djgentelellaurls + [
                    ...
                  ]

Usage
_________


In forms

.. code:: python

    from djgentelella.forms.forms import GTForm
    from djgentelella.widgets import core as genwidgets

    class myform(GTForm, forms.ModelForm):
        class Meta:
            model = MyObject
            fields = '__all__'
            widgets = {
                'name': genwidgets.TextInput,
                'borddate': genwidgets.DateInput,
                'email': genwidgets.EmailMaskInput
            }

In templates working with forms

.. code:: html

     {{ form.as_plain }}
     {{ form.as_inline }}
     {{ form.as_horizontal }}

In templates using base template

.. code:: html

    {% extends 'gentelella/base.html' %}

Take a look this file to note the template block that you can overwrite

Test
__________

The whole suite, minus the browser tests:

.. code:: bash

    make test

The package tests live outside the demo directory, so discovery does not reach
them on its own. This is what CI runs:

.. code:: bash

    cd demo
    python manage.py test --exclude-tag=selenium
    python manage.py test djgentelella.tests
    python manage.py test djgentelella.blog.tests

The Selenium tests are tagged ``selenium`` and excluded by default. They drive a
real browser against MailHog, so start it first:

.. code:: bash

    make mailhog
    make test-selenium

Lint
__________

.. code:: bash

    make lint       # pycodestyle (style) + ruff (import placement)
    make lint-fix   # apply the mechanical fixes

Two checkers on purpose: **pycodestyle** owns style, with its options in
``setup.cfg`` (it does not read ``pyproject.toml``), and **ruff** owns
``PLC0415``, which keeps imports at the top of the module. A function-level
import is allowed only when it is genuinely required — an optional dependency,
an ``AppConfig.ready()`` that runs before the app registry is populated, or a
circular import — and must carry ``# noqa: PLC0415`` plus a comment naming the
reason.

Run the demo
---------------

.. code:: bash

    cd demo
    python manage.py migrate
    python manage.py createdemo
    python manage.py demomenu

And More see demo app.

Run the demo with Makefile
-----------------------------

.. code:: bash

    make init_demo

``make help`` lists the rest of the targets (demo server, MailHog, translations,
build and release).

Notes for development
____________________________

`base.js` is autogenerated so you need to call

.. code:: bash

    python manage.py createbasejs

Remember update the package version before make deploy it on server.

Translation
____________________________

To add a new translation for a word there are two options:

.. code:: bash

    django-admin makemessages --all

This command adds words that are inside django templates to ``locale/es/LC_MESSAGES/django.po``, there these words can be translated.

To add a word you can use the following syntax.

.. code:: html

    {% trans "new_word" %}

For words used in JavaScript files, the following command must be executed.

.. code:: bash

    django-admin makemessages -d djangojs -l es  --ignore *.min.js

This command adds words that are inside the ``gettext`` js function, to ``locale/es/LC_MESSAGES/djangojs.po``, there these words can be translated.

Here is an example of ``gettext`` implementation:

.. code:: js

    alert(gettext("new_word"))

Notes for releases
____________________________

Patch pylp first — every clean environment needs it
------------------------------------------------------

``make sdist`` bundles the vendor assets with ``python -m pylp``, and **pylp
fails on every supported Python version out of the box**::

    TypeError: Passing coroutines is forbidden, use tasks explicitly.

pylp 0.2.10 is the current release and its code dates from 2017. It hands
coroutines straight to ``asyncio.wait()``, which Python deprecated in 3.8 and
removed in 3.11 — and 3.11 is this project's floor. The project is unmaintained,
so this will not be fixed upstream: **the patch has to be reapplied in every new
virtualenv**, or the release build stops there.

Edit line 53 of ``{venv}/lib/python3.x/site-packages/pylp/cli/run.py``:

.. code:: python

    # as shipped
    await asyncio.wait(map(lambda runner: runner.future, running))

    # required
    await asyncio.wait(map(lambda runner: asyncio.create_task(runner.future), running))

Same one-liner, applied in place:

.. code:: bash

    sed -i 's/lambda runner: runner\.future/lambda runner: asyncio.create_task(runner.future)/' \
        "$(python -c 'import pylp.cli.run as m; print(m.__file__)')"

The file is indented with tabs — keep them if you edit it by hand.

Build module
---------------

A bare virtualenv has no ``build`` module, so ``python3 -m build`` fails until:

.. code:: bash

    python -m pip install build

It is already listed in ``test_requirements.txt``, so
``pip install -r test_requirements.txt`` covers it.

License
____________________________

GPL-2.0-or-later — see ``LICENSE.txt``, which carries the GPL v2 text.
