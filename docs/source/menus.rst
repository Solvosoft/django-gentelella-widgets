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
     - If True, ``url_name`` names a registered menu widget (see
       `Custom Widgets`_)
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
   * - ``site``
     - ForeignKey
     - The ``Site`` the item belongs to; empty (the default) shows it on every
       site. See :doc:`sites`
   * - ``condition``
     - JSONField
     - A condition of :doc:`authorization` that must hold, besides the
       permissions, for the item to be shown; empty (the default) means none
   * - ``key``
     - SlugField
     - Optional natural key: unique among the items of its Site (or among the
       global items). An exported menu names the item by it, so importing it
       again updates the item in place. See `Exporting and Importing a Menu`_


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


A Design Page
-------------

A ``url_name`` of ``page:<path>`` (not reversed) links the page of
:doc:`designs` published at that path:

.. code:: python

    MenuItem.objects.create(
        title='Clients',
        url_name='page:sales/clients',  # -> /designs/sales/clients
        category='sidebar',
    )

Without ``djgentelella.designs`` installed there is no such route, and the
item links its ``url_name`` as it is instead of breaking the menu.

A page answers at its path with and without a trailing slash. With
``GT_MENU_DESIGN_PAGE_SLASH = True`` (off by default) the link of a design
page -- a ``page:<path>`` item and a reversed ``gt-design-page`` -- ends in
``/`` (``/designs/sales/clients/``): for a project that visits its pages
with the slash, so a breadcrumb or an active item that compares the link
with ``request.path`` matches.

It stays off by default: turning it on changes every link to a design page
already drawn, and the projects on top of djgentelella assert the link
without the slash. To adopt it, set it, then update whatever compares those
links as text (tests, breadcrumbs built by hand, an active item matched by
``startswith``); the pages keep answering at both paths, so no link breaks
in the meantime.


The Link of an Item in Python
-----------------------------

``djgentelella.menu.item_url(item, context=None, *, fail_silently=False)``
returns the ``href`` the menu tags draw for ``item``: ``url_name`` as it is,
reversed (``reversed_args`` and ``reversed_kwargs`` read from ``context``,
the template context or a dict such as ``{'request': request}``), the design
page of ``page:<path>``, or ``''`` for a widget. A view that walks the menu
tree -- breadcrumbs, a site map -- links items the same way with it:

.. code:: python

    from djgentelella.menu import item_url

    href = item_url(item, {'request': request}, fail_silently=True)

A reverse that fails raises ``NoReverseMatch``; with ``fail_silently=True``
it returns ``''``.


The Visible Items in Python
---------------------------

The menu tags load the whole menu of the current Site once per request --
every item, its permissions and their content types, three queries however
large the tree is -- and walk it in memory. The tree is kept on the request,
so the top bar, the sidebar and the footer of one page share that load. An
item created during a request shows from the next one.

The same tree is public, for breadcrumbs or a site map that must not query
item by item:

.. code:: python

    from djgentelella.menu import item_visible, menu_tree, visible_items

    # [(item, level), ...] of a category, depth first, as the menu draws it:
    # an item shows when it and all of its ancestors are visible.
    for item, level in visible_items(request, 'sidebar'):
        ...

    tree = menu_tree(request)          # the Site of the request
    tree.roots('main')                 # roots of a category, by position
    tree.children(item)                # children, by id
    item_visible(item, request)        # its permissions and its condition

Roots are ordered by ``position`` and children by ``id``. Both honour the Site
of the request and the override of a global item by a Site item, like the
tags. ``PLACEHOLDER_URL_NAMES`` and ``override_identity`` live in
``djgentelella.menu`` and are still importable from
``djgentelella.templatetags.gentelellamenu``.


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

A menu item with ``is_widget=True`` is drawn by a class instead of a link.
The menu only builds classes the project **declares** as menu widgets, so
whoever edits a menu item cannot make every page import and call any class:

* djgentelella's own (``djgentelella.menu_widgets.palette.PalleteWidget``,
  ``djgentelella.notification.widgets.NotificationMenu``) register themselves;
* a class decorated with ``djgentelella.menu.register_menu_widget`` (named by
  its dotted path, and by ``name=`` when given);
* a class defined in the ``menu_widgets`` module of an installed app
  (``myapp/menu_widgets.py``), found when the menu first needs a widget;
* a dotted path listed in ``settings.GT_MENU_WIDGETS``.

.. code:: python

    # myapp/widgets.py
    from djgentelella.menu import register_menu_widget

    @register_menu_widget
    class ClockMenu:
        def __init__(self, context):
            self.context = context   # 'id', 'item' and the menu environment

        def render(self):
            return '<span class="clock"></span>'

An item that names anything else is left out of the menu, with a warning in
the ``djgentelella.menu`` log (once per name); its class is never imported.
``MenuItem.clean()`` -- the admin -- refuses it. Up to 0.8 the menu imported
any ``url_name`` of a widget item; to keep a widget of your own working,
decorate it, move it to ``<app>/menu_widgets.py`` or list its path in
``GT_MENU_WIDGETS``. ``djgentelella.menu.get_menu_widget(name)``,
``is_menu_widget(name)`` and ``registered_menu_widgets()`` answer which ones
the project has.

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


Exporting and Importing a Menu
------------------------------

``djgentelella.menu`` reads and writes the menu of one Site as plain data,
without pks, for fixtures, copies between Sites and application builders:

.. code:: python

    from djgentelella.menu import export_tree, import_tree, validate_tree

    data = export_tree(site)                # a list of trees; site=None: global
    roots, errors = import_tree(data, other_site)              # replace=True
    roots, errors = import_tree(data, other_site, replace=False)

Each node carries ``key``, ``title``, ``url_name``, ``category``,
``is_reversed``, ``reversed_kwargs``, ``reversed_args``, ``is_widget``,
``icon``, ``only_icon``, ``position``, ``condition``, ``permissions``
(``['app_label.codename', ...]``) and ``children``. A root of a Site under a
global item names it in ``global_parent`` (``key``, ``title``, ``url_name``,
``category``: by key when it has one).

``import_tree`` checks everything first with ``validate_tree`` -- the fields
and their types, keys (slugs, not repeated), existing permissions, valid
conditions, registered widgets, the global parent and at most
``MAX_MENU_DEPTH`` (10) levels -- and returns ``(None, errors)`` without
writing anything when something is wrong (``errors`` are ``(path, message)``
tuples). Otherwise it writes the whole menu in one transaction: an item whose
``key`` names an item of that scope is updated in place (it keeps its pk), any
other is created, and with ``replace`` (the default) the items of the scope
the data does not name are deleted. The global items are never touched by the
import of a Site.

``validate_tree(data, site)`` takes a ``Site`` that is not saved yet, to check
a menu -- its ``global_parent`` included -- before creating the Site it is for;
``import_tree`` needs the Site saved.

An item whose parent is out of the exported scope (an item of another Site,
or, in the global menu, of a Site) is exported as a root. To be told, pass a
list:

.. code:: python

    warnings = []
    data = export_tree(site, warnings=warnings)
    for warning in warnings:        # Error(path, message), path like '$[2]'
        print(warning)

The data returned is the same with or without ``warnings``.

``MenuItem.objects.get_by_natural_key(key, site_domain=None)`` finds an item
by its key. ``MenuItem`` has no ``natural_key()`` on purpose: the items
without a key would break ``dumpdata --natural-foreign``.

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


Responsive behaviour
====================

The breakpoint is 992px, and it is the same one in ``gentelella/css/sidebar.css``
and in ``custom.js`` (a single ``matchMedia``), so the stylesheet and the script
can never disagree about which layout is in force.

**At 992px and above** the sidebar is a fixed, full-height column. The menu
itself scrolls inside it, and the sidebar-footer icons sit in a wrapping row at
the bottom of that column -- in flow, so they can never cover a menu entry nor
grow wider than the sidebar. ``#menu_toggle`` collapses the column to the 70px
icon rail; a submenu then opens as a flyout beside the entry it belongs to,
positioned by ``positionRailFlyout`` in ``custom.js`` (it has to be
``position: fixed``, because the scrolling menu would clip an absolutely
positioned child to 70px).

**Below 992px** the sidebar becomes an off-canvas drawer. ``#menu_toggle``
slides it over the page at its full width with a backdrop -- labels, chevrons
and all three levels intact -- and clicking the backdrop, pressing ``Escape`` or
following a leaf link closes it again. The body stays in ``nav-md`` throughout;
only ``body.sidebar-open`` is toggled. The page behind does not reflow, because
``.right_col`` and ``.top_nav`` are already full width at this size.

In the top navigation bar, a nested level opens on click as well as on hover, so
it is reachable on a touch screen. Above the breakpoint it unfolds to the left
of its parent (the bar is right-aligned, so opening rightwards would leave the
window); below it, nested levels unfold as an indented block inside the parent
menu, which always fits, and ``custom.js`` caps the menu's height to the room
left below it so a short window can still scroll to the last entry.

Everything above is covered by ``demoapp/tests/selenium/test_menu.py``, which
sweeps eight viewport sizes and asserts of every entry that it is on screen and
is the topmost element at its own centre -- that is, genuinely clickable rather
than merely present in the DOM.

If you ship your own theme through the ``site_theme`` setting, note that
``sidebar.css`` is linked *after* it precisely so these rules survive the
change; ``site_extracss`` is linked after both and can still override them.


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
    Creates a simple menu structure for basic testing. With ``--with-site`` it
    also creates a second Site with menu items of its own (see :doc:`sites`).

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
