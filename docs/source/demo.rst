Demo Site
===========

The repository includes a demo Django project that showcases all features of Django Gentelella Widgets.

Quick Start with Make
-----------------------

The fastest way to run the demo is using the provided Makefile commands:

.. code:: bash

    # Clone the repository
    git clone https://github.com/Solvosoft/django-gentelella-widgets.git
    cd django-gentelella-widgets

    # Create and activate virtual environment
    python3.11 -m venv env
    source env/bin/activate

    # Install dependencies
    pip install -r requirements.txt
    pip install requests

    # Initialize demo (migrate, create data, menu, superuser)
    make init_demo

    # Load static assets
    cd demo && python manage.py loaddevstatic && cd ..

    # Run the server
    make run

Then visit ``http://localhost:8000/`` in your browser.

Available Make Commands
-------------------------

The Makefile provides several useful commands:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Command
     - Description
   * - ``make init_demo``
     - Full setup: migrate, create demo data, menu, and superuser
   * - ``make run``
     - Start the development server
   * - ``make migrate``
     - Run makemigrations and migrate
   * - ``make menu``
     - Regenerate the sidebar menu
   * - ``make test``
     - Run the whole unit suite (every label, no selenium), as the CI does
   * - ``make lint``
     - Check code style with pycodestyle
   * - ``make docs``
     - Build Sphinx documentation
   * - ``make clean``
     - Remove build artifacts and compiled files
   * - ``make messages``
     - Extract translatable strings
   * - ``make trans``
     - Compile translations

Translations
------------

The ``.po`` catalogs are versioned; the compiled ``.mo`` files are not
(``.gitignore``). ``make trans`` compiles them, ``make sdist`` does it before
building the package, and the CI does it before running the tests, so the
suite runs with the Spanish catalog the demo (``LANGUAGE_CODE = 'es'``) loads.
The suite passes with and without the ``.mo`` files: a test that compares a
message in English wraps it in ``translation.override('en')``.

``make messages`` updates both catalogs from the ``djgentelella`` directory
with ``gtmakemessages``, a ``makemessages`` that for the ``djangojs`` domain
also reads ``pg_gettext()`` and the inline ``<script>`` blocks of templates,
so ``--no-obsolete`` keeps their translations. The tests, the vendors, the
bundles and the generated ``base.js`` are left out.

Manual Setup
--------------

If you prefer to set up the demo manually, follow these steps:

1. Create Virtual Environment
"""""""""""""""""""""""""""""""

.. code:: bash

    python3.11 -m venv env
    source env/bin/activate   # On Windows: env\Scripts\activate

2. Install Dependencies
"""""""""""""""""""""""""

.. code:: bash

    pip install -r requirements.txt
    pip install requests

3. Run Migrations
"""""""""""""""""""

.. code:: bash

    cd demo
    python manage.py migrate

4. Create Demo Data
"""""""""""""""""""""

.. code:: bash

    python manage.py createdemo

5. Create Sidebar Menu
""""""""""""""""""""""""

.. code:: bash

    python manage.py demomenu

6. Load Static Assets
"""""""""""""""""""""""

.. code:: bash

    python manage.py loaddevstatic

7. Create Superuser (Optional)
""""""""""""""""""""""""""""""""

.. code:: bash

    python manage.py createsuperuser

8. Run Development Server
"""""""""""""""""""""""""""

.. code:: bash

    python manage.py runserver

Demo Features
---------------

The demo site includes examples of:

**Forms & Widgets**

- All core input widgets (text, number, email, etc.)
- Select widgets with Select2 integration
- Date and time pickers
- File upload with chunked upload support
- Masked inputs (phone, credit card, etc.)
- WYSIWYG editors (TinyMCE, Summernote)

**Data Tables**

- Server-side pagination
- Column filtering
- Global search
- Sorting
- Export functionality

**CRUD Views**

- List, Create, Update, Delete views
- Permission management
- Pagination options
- Search and filtering

**Advanced Features**

- Blog system
- Notification system
- History/audit trail
- Trash/soft delete
- Digital signatures

Demo Credentials
------------------

If you used ``make init_demo``, you were prompted to create a superuser.

For admin access, visit ``http://localhost:8000/admin/`` and log in with your superuser credentials.

Running Tests
---------------

Run the test suite to verify everything is working:

.. code:: bash

    make test

Or manually:

.. code:: bash

    cd demo
    python manage.py test

For Selenium tests (requires browser driver):

.. code:: bash

    cd demo
    python manage.py test demoapp.tests.selenium

A project built on djgentelella reuses two pieces in its own browser tests:

- ``djgentelella.testing.mouse_click(driver, element)`` clicks with the
  mouse after bringing the element to the centre of the viewport *without
  animation*. Bootstrap sets ``scroll-behavior: smooth``, so after a plain
  ``scrollIntoView()`` the page is still moving when the click lands, and
  Chrome answers ``ElementClickInterceptedException`` or clicks something
  else. ``scroll_instantly(driver, element)`` only scrolls. The demo's
  ``SeleniumTestCase`` has both as methods (``self.mouse_click(css or
  element)``).
- ``djgentelella.utils.load_default_settings()`` in ``setUp`` brings back the
  settings the migrations create, which the flush after every live server
  test removes (``default_settings = True`` in the demo's base). See
  :doc:`settings`.

