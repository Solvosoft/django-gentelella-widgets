===========
Menu System
===========

Django Gentelella Widgets provides a flexible menu system through the ``MenuItem`` model. Menus can be displayed in the top navigation bar, sidebar, or sidebar footer, and support hierarchical structures, permissions, and custom widgets.


MenuItem Model
==============

The ``MenuItem`` model stores menu configuration in the database and supports tree-based hierarchies using ``django-tree-queries``.

Fields
------

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Field
     - Type
     - Description
   * - ``title``
     - CharField
     - Display text for the menu item
   * - ``url_name``
     - CharField
     - URL pattern name (for reversed URLs) or direct URL path
   * - ``category``
     - CharField
     - Menu location: ``'main'``, ``'sidebar'``, or ``'sidebarfooter'``
   * - ``is_reversed``
     - BooleanField
     - If True, ``url_name`` is a Django URL name to be reversed
   * - ``reversed_kwargs``
     - CharField
     - Keyword arguments for URL reverse (format: ``key:value,key2:value2``)
   * - ``reversed_args``
     - CharField
     - Positional arguments for URL reverse (comma-separated, can use context like ``request.user.pk``)
   * - ``is_widget``
     - BooleanField
     - If True, ``url_name`` is a Python path to a widget class
   * - ``icon``
     - CharField
     - CSS class for icon (e.g., ``'fa fa-home'``)
   * - ``only_icon``
     - BooleanField
     - If True, only display icon without title (useful for footer)
   * - ``position``
     - IntegerField
     - Order of items within the same parent
   * - ``parent``
     - ForeignKey
     - Parent MenuItem for hierarchical menus (None for top-level)
   * - ``permission``
     - ManyToManyField
     - Permissions required to view this menu item


Menu Categories
===============

djgentelella supports three menu locations:

**main** - Top Navigation Bar
    Horizontal menu in the top navigation area. Supports dropdowns for child items.

**sidebar** - Left Sidebar
    Vertical menu in the left sidebar. Supports multiple levels of nesting with collapsible sections.

**sidebarfooter** - Sidebar Footer
    Icons displayed at the bottom of the sidebar. Typically used for settings, logout, and help widgets.


Template Tags
=============

Load the menu template tags in your template:

.. code:: html

    {% load gentelellamenu %}

Available Tags
--------------

``{% top_menu %}``
    Renders the top navigation bar menu (category ``'main'``).

``{% sidebar_menu %}``
    Renders the sidebar menu (category ``'sidebar'``).

``{% footer_sidebar_menu %}``
    Renders the sidebar footer icons (category ``'sidebarfooter'``).

``{% render_external_widget %}``
    Renders content for any menu widgets. Place this where widget content should appear.

``{% render_menu_js_widget %}``
    Renders JavaScript for menu widgets. Place this in the JS block.

``{% render_extra_html_menu %}``
    Renders additional HTML for menu widgets (modals, etc.).

Example Template
----------------

.. code:: html

    {% extends 'gentelella/base.html' %}
    {% load gentelellamenu %}

    {% block sidebar %}
        {% sidebar_menu %}
    {% endblock %}

    {% block top_navigation %}
        {% top_menu %}
    {% endblock %}

    {% block content %}
        {% render_external_widget %}
        <!-- Your content here -->
    {% endblock %}

    {% block js %}
        {% render_menu_js_widget %}
    {% endblock %}


Creating Menu Items
===================

Basic Link
----------

A simple link without URL reversal:

.. code:: python

    from djgentelella.models import MenuItem

    MenuItem.objects.create(
        title='Home',
        url_name='/',
        category='sidebar',
        is_reversed=False,
        icon='fa fa-home'
    )


With Django URL Reverse
-----------------------

Link to a named URL pattern:

.. code:: python

    MenuItem.objects.create(
        title='Dashboard',
        url_name='dashboard',
        category='sidebar',
        is_reversed=True,
        icon='fa fa-tachometer'
    )


With URL Parameters (kwargs)
----------------------------

Pass keyword arguments to the URL reverse:

.. code:: python

    MenuItem.objects.create(
        title='Edit User',
        url_name='user_edit',
        category='sidebar',
        is_reversed=True,
        reversed_kwargs='pk:1',  # Results in reverse('user_edit', kwargs={'pk': 1})
        icon='fa fa-user'
    )


With Dynamic Context
--------------------

Access template context values like ``request.user.pk``:

.. code:: python

    MenuItem.objects.create(
        title='My Profile',
        url_name='user_profile',
        category='sidebar',
        is_reversed=True,
        reversed_args='request.user.pk',  # Dynamic value from context
        icon='fa fa-user-circle'
    )


Hierarchical Menus
------------------

Create parent-child relationships for nested menus:

.. code:: python

    # Create parent
    settings_menu = MenuItem.objects.create(
        parent=None,
        title='Settings',
        url_name='#',
        category='sidebar',
        is_reversed=False,
        icon='fa fa-cog'
    )

    # Create children
    MenuItem.objects.create(
        parent=settings_menu,
        title='General',
        url_name='settings_general',
        category='sidebar',
        is_reversed=True,
        icon='fa fa-sliders'
    )

    MenuItem.objects.create(
        parent=settings_menu,
        title='Security',
        url_name='settings_security',
        category='sidebar',
        is_reversed=True,
        icon='fa fa-shield'
    )


Custom Widgets
--------------

Use a custom widget class for special menu functionality:

.. code:: python

    from django.urls import reverse

    MenuItem.objects.create(
        title='',  # Widget handles its own title
        url_name='djgentelella.notification.widgets.NotificationMenu',
        category='main',
        is_reversed=False,
        reversed_args=reverse('notifications'),  # API URL for widget
        is_widget=True,
        icon='fa fa-bell'
    )


With Permissions
----------------

Restrict menu visibility based on Django permissions:

.. code:: python

    from django.contrib.auth.models import Permission

    perm = Permission.objects.get(codename='can_manage_users')

    item = MenuItem.objects.create(
        title='User Management',
        url_name='user_list',
        category='sidebar',
        is_reversed=True,
        icon='fa fa-users'
    )
    item.permission.add(perm)  # Only visible to users with this permission


Sidebar Footer Items
--------------------

Create icon-only items for the sidebar footer:

.. code:: python

    MenuItem.objects.create(
        title='Logout',
        url_name='/accounts/logout/',
        category='sidebarfooter',
        is_reversed=False,
        icon='fa fa-power-off',
        only_icon=True
    )


Using Django Admin
==================

Menu items can also be managed through the Django admin interface. The ``MenuItem`` model is registered with the admin and supports:

- Creating and editing menu items
- Setting parent-child relationships
- Assigning permissions
- Ordering items by position


Management Commands
===================

The demo application includes commands for creating sample menus:

``python manage.py createdemo``
    Creates a full demo menu structure with all widget examples, blog, dashboard, and various form widgets.

``python manage.py demomenu``
    Creates a simple menu structure for basic testing.

These commands can serve as reference for creating your own menu structures programmatically.


Complete Example
================

Here's a complete example creating a typical application menu:

.. code:: python

    from django.urls import reverse
    from djgentelella.models import MenuItem

    def create_application_menu():
        # Clear existing menu
        MenuItem.objects.all().delete()

        # Home section
        home = MenuItem.objects.create(
            title='Home',
            url_name='/',
            category='sidebar',
            is_reversed=False,
            icon='fa fa-home',
            position=0
        )

        # Dashboard under Home
        MenuItem.objects.create(
            parent=home,
            title='Dashboard',
            url_name='dashboard',
            category='sidebar',
            is_reversed=True,
            icon='fa fa-tachometer',
            position=0
        )

        # Reports section
        reports = MenuItem.objects.create(
            title='Reports',
            url_name='#',
            category='sidebar',
            is_reversed=False,
            icon='fa fa-bar-chart',
            position=1
        )

        MenuItem.objects.create(
            parent=reports,
            title='Sales Report',
            url_name='report_sales',
            category='sidebar',
            is_reversed=True,
            icon='fa fa-line-chart',
            position=0
        )

        MenuItem.objects.create(
            parent=reports,
            title='User Report',
            url_name='report_users',
            category='sidebar',
            is_reversed=True,
            icon='fa fa-users',
            position=1
        )

        # Footer items
        MenuItem.objects.create(
            title='Settings',
            url_name='settings',
            category='sidebarfooter',
            is_reversed=True,
            icon='fa fa-cog',
            only_icon=True,
            position=0
        )

        MenuItem.objects.create(
            title='Logout',
            url_name='/accounts/logout/',
            category='sidebarfooter',
            is_reversed=False,
            icon='fa fa-power-off',
            only_icon=True,
            position=1
        )

        # Notification widget in top bar
        MenuItem.objects.create(
            title='Notifications',
            url_name='djgentelella.notification.widgets.NotificationMenu',
            category='main',
            is_reversed=False,
            reversed_args=reverse('notifications'),
            is_widget=True,
            icon='fa fa-bell',
            position=0
        )
