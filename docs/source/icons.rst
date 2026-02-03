=====
Icons
=====

Django Gentelella Widgets includes several icon libraries that can be used throughout your application for navigation, buttons, status indicators, and more.

Font Awesome 4.7.0
==================

Font Awesome is the primary icon library used in djgentelella. It is automatically loaded when using the base template.

Installation
------------

Font Awesome is included via ``loaddevstatic`` and bundled into the vendor files:

.. code:: bash

    python manage.py loaddevstatic

Usage
-----

Use the ``<i>`` tag with Font Awesome classes:

.. code:: html

    <i class="fa fa-home"></i>
    <i class="fa fa-user"></i>
    <i class="fa fa-cog"></i>

Common Icons in djgentelella
----------------------------

**Navigation:**

- ``fa fa-home`` - Home
- ``fa fa-bars`` - Menu/hamburger
- ``fa fa-chevron-down`` - Expand
- ``fa fa-chevron-right`` - Navigate

**Actions:**

- ``fa fa-plus`` - Add
- ``fa fa-plus-circle`` - Add (circled)
- ``fa fa-pencil`` - Edit
- ``fa fa-trash`` - Delete
- ``fa fa-save`` - Save
- ``fa fa-download`` - Download
- ``fa fa-upload`` - Upload

**Status:**

- ``fa fa-check`` - Success/complete
- ``fa fa-times`` - Error/close
- ``fa fa-exclamation-triangle`` - Warning
- ``fa fa-info-circle`` - Information
- ``fa fa-spinner fa-spin`` - Loading

**Objects:**

- ``fa fa-user`` - User
- ``fa fa-users`` - Users/group
- ``fa fa-file`` - File
- ``fa fa-folder`` - Folder
- ``fa fa-calendar`` - Calendar
- ``fa fa-table`` - Table/data
- ``fa fa-cog`` - Settings
- ``fa fa-envelope`` - Email/notification

Reference
---------

For a complete list of available icons, see the `Font Awesome 4.7 Cheatsheet <https://fontawesome.com/v4/cheatsheet/>`_.


Flag Icons 6.6.6
================

Flag Icons provides 260+ country and region flags as CSS icons.

Installation
------------

Flag Icons are loaded via ``loaddevstatic`` but must be explicitly enabled in your templates.

Enable in your template by setting ``use_flags`` to true:

.. code:: html

    {% extends 'gentelella/base.html' %}
    {% load gtsettings %}

    {% block pre_head %}
        {% define_true "use_flags" %}
    {% endblock %}

Usage
-----

Use the ``<i>`` tag with flag-icon classes. Country codes follow ISO 3166-1 alpha-2 format:

.. code:: html

    <i class="flag-icon flag-icon-us"></i>  <!-- United States -->
    <i class="flag-icon flag-icon-gb"></i>  <!-- United Kingdom -->
    <i class="flag-icon flag-icon-es"></i>  <!-- Spain -->
    <i class="flag-icon flag-icon-cr"></i>  <!-- Costa Rica -->
    <i class="flag-icon flag-icon-de"></i>  <!-- Germany -->
    <i class="flag-icon flag-icon-jp"></i>  <!-- Japan -->

Square Flags
------------

For square flags (1:1 ratio), add the ``flag-icon-squared`` class:

.. code:: html

    <i class="flag-icon flag-icon-us flag-icon-squared"></i>


Friconix
========

Friconix is a modern icon library loaded via JavaScript.

Usage
-----

Friconix icons use the ``fi`` prefix:

.. code:: html

    <i class="fi fi-xnsuxx-plus"></i>

Refer to the Friconix documentation for available icons.


Timeline/StoryMap Icons
=======================

Specialized icons for timeline and storymap widgets are included when using readonly widgets.

Enable these icons by setting ``use_readonlywidgets``:

.. code:: html

    {% extends 'gentelella/base.html' %}
    {% load gtsettings %}

    {% block pre_head %}
        {% define_true "use_readonlywidgets" %}
    {% endblock %}


Using Icons in MenuItem
=======================

When creating menu items, you can set the ``icon`` field to display an icon next to the menu title.

.. code:: python

    from djgentelella.models import MenuItem

    MenuItem.objects.create(
        title='Dashboard',
        url_name='dashboard',
        category='sidebar',
        is_reversed=True,
        icon='fa fa-tachometer',  # Font Awesome icon
        only_icon=False
    )

For footer sidebar items where you want only the icon displayed:

.. code:: python

    MenuItem.objects.create(
        title='Logout',
        url_name='/accounts/logout/',
        category='sidebarfooter',
        is_reversed=False,
        icon='fa fa-power-off',
        only_icon=True  # Only show the icon, not the title
    )
