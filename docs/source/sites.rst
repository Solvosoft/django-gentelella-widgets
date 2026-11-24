=========================================
Sites: menus and settings per application
=========================================

One djgentelella installation can serve several applications, each one a
``django.contrib.sites`` ``Site``, with **its own menus and its own
settings**. A ``MenuItem`` or a ``GentelellaSettings`` row with an empty
``site`` is *global*: every Site sees it, and a project that never creates a
second Site behaves exactly as before.

The rule is the same everywhere in djgentelella:

    the value with ``site=<current Site>`` wins; when there is none, the one
    with ``site=NULL`` (global) is used.


Installation
============

``django.contrib.sites`` is required: ``MenuItem.site`` and
``GentelellaSettings.site`` are foreign keys to ``sites.Site``. Add it to
``INSTALLED_APPS`` and set ``SITE_ID`` (Django's own views, such as
``LoginView``, need it to find a Site for unknown hosts):

.. code:: python

    INSTALLED_APPS = [
        # ...
        'djgentelella',
        'django.contrib.sites',
    ]
    SITE_ID = 1

Then ``python manage.py migrate``. The migration ``0022_site_scoping`` leaves
every existing menu item and setting global (``site=NULL``). It also makes the
key of a setting unique per Site. If the table has two global rows with the
same key (``set_settings`` already failed on them) the migration stops with
``DuplicateGlobalSettings``, listing the ``pk`` and value of each row, and
deletes nothing: keep one row per key and run ``migrate`` again. The migration
is rolled back as a whole, so nothing of it is applied in between.

The option of an integer ``site_id`` without a foreign key, for projects
without ``django.contrib.sites``, was discarded: the app is part of Django,
costs one table, and a real foreign key gives the admin filter, ``CASCADE``
when a Site is deleted, and joins.


The current Site
================

.. code:: python

    from djgentelella.sites import get_current_site, site_q

    site = get_current_site(request)   # a Site, or None
    MenuItem.objects.filter(site_q(site))

``get_current_site(request=None)`` looks for the Site in this order:

1. ``request.site``, when a middleware already put it there:
   Django's ``CurrentSiteMiddleware``, or an application middleware that
   resolves it by host or by path prefix. ``request.site = None`` means "no
   Site" and is respected; an object that is not a ``Site`` row
   (``RequestSite``) counts as no Site.
2. The Site whose ``domain`` is the host of the request, with the port
   (``example.com:8000``) and then without it, case-insensitive.
3. ``None``: menus and settings are the global ones.

It also returns ``None`` without a request (management commands, Celery
tasks) and when ``django.contrib.sites`` is not installed. The answer is
cached on the request, so a page resolves it once.

**SITE_ID is not a fallback.** With ``SITE_ID = 1`` and no Site for the host,
``get_current_site`` returns ``None``, not Site 1: otherwise every host
without its own Site would show the menus of Site 1 (by default
``example.com``) instead of the global ones. To let ``SITE_ID`` decide, add
``django.contrib.sites.middleware.CurrentSiteMiddleware``: it sets
``request.site`` to the Site of the host, or to ``SITE_ID`` when the host has
none, and step 1 uses it.

``site_q(site, field='site')`` is ``Q(site=site) | Q(site__isnull=True)``,
and only ``Q(site__isnull=True)`` when ``site`` is ``None``. ``field`` names
the foreign key, or a path to it (``'page__site'``). Any model with an
optional ``site`` foreign key uses it to apply the rule.

A request of another Site
-------------------------

Some questions have to be asked on behalf of a Site that is not the one of
the current request: the export formats of a report of another App (its
layouts are formats only there), whether a condition holds for the user of a
subscription, a flag of that Site. ``site_request(site, user=None)`` builds a
synthetic ``GET`` request of that Site:

.. code:: python

    from djgentelella.datasources.export import available_formats
    from djgentelella.sites import site_request

    request = site_request(report.site, user=subscription.user)
    if fmt not in available_formats(request):
        ...

It is a real ``HttpRequest`` whose ``site`` is the Site row (so
``get_current_site`` returns it), with ``user`` (an ``AnonymousUser`` when it
is ``None``, as ``ConditionRequest`` does for the system), ``method='GET'``,
``path='/'``, empty ``GET``/``POST``/``COOKIES``, the Site's ``domain`` as the
host (``localhost`` for the global scope) and ``is_site_request = True``.
``site`` may be a ``Site``, its id or ``None`` (global); an id of no Site
raises ``ValueError``. No middleware has run on it: there is no session, and
``get_host()`` checks the domain against ``ALLOWED_HOSTS`` as for any
request.

Use it where code expects a request (exporters, data sources, templates);
``djgentelella.authorization.ConditionRequest`` is the lighter stand-in that
only conditions and authorizations need. ``resolve_site(site)`` is the lookup
both share: the Site row of a ``Site``, an id or ``None``.


Menus
=====

``MenuItem.site`` is optional. ``{% top_menu %}``, ``{% sidebar_menu %}`` and
``{% footer_sidebar_menu %}`` show, on every level of the tree, the global
items and those of the current Site:

- **The hierarchy is not mixed.** A child that belongs to another Site is
  hidden even when its parent is global; a global item with only hidden
  children is drawn as a plain link, not as a dropdown.
- **Override.** On one level (the roots of a category, or the children of one
  item), an item of the Site with the same ``url_name`` and ``category`` as a
  global one replaces it, in its place and with its own children: the global
  item and its whole branch are not shown on that Site.

  Items whose ``url_name`` is only a placeholder (``''``, ``'/'``, ``'#'``,
  as dropdown roots usually have) share it, so for them the ``title`` must
  match too: a Site item ``'Base 2'`` with ``url_name='/'`` replaces the
  global ``'Base 2'``, and the global ``'Base 1'`` and ``'Base 3'`` stay.
  The override is checked level by level, among siblings: an item does not
  replace one of the same ``url_name`` in another branch of the tree.

.. code:: python

    from django.contrib.sites.models import Site
    from djgentelella.models import MenuItem

    ventas = Site.objects.get(domain='ventas.example.com')
    # Only on ventas
    MenuItem.objects.create(title='Pedidos', url_name='pedidos-list',
                            is_reversed=True, category='main', site=ventas)
    # Replaces the global item with url_name='home' on ventas
    MenuItem.objects.create(title='Inicio ventas', url_name='home',
                            is_reversed=True, category='main', site=ventas)

The template tags take the Site from ``request`` (the ``request`` context
processor must be enabled, as djgentelella already requires).


Settings
========

``GentelellaSettings.site`` is optional, and ``(key, site)`` is unique:
one global value per key and one per key and Site.

.. code:: python

    from djgentelella.utils import get_settings, set_settings

    set_settings('site_title', 'My company')               # global
    set_settings('site_title', 'Sales', site=ventas)       # only ventas

    get_settings('site_title')                    # 'My company'
    get_settings('site_title', ventas)            # 'Sales'
    get_settings('site_title', site=other_site)   # 'My company' (fallback)

- ``get_settings(key, site=None, none_asdefault=False)``: the Site's value,
  else the global one, else ``''`` (``None`` with ``none_asdefault=True``).
  ``site`` is a ``Site``, a Site id or ``None``. Without ``site`` it is the
  global value, as before; the old positional form
  ``get_settings(key, True)`` still means ``none_asdefault``.
- ``set_settings(key, value, site=None)``: creates or updates the value of that
  scope.
- In both, ``site`` may be a ``Site``, its id (an ``int`` or a string of
  digits) or ``None``. A ``RequestSite`` is global, as for
  ``get_current_site``. Anything else -- an unsaved ``Site``, a domain string
  -- raises ``ValueError`` or ``TypeError`` (``djgentelella.sites.site_pk``).
- ``{% get_settings 'site_title' %}`` uses the Site of the request.

**Cache.** Every scope is cached on its own, under ``(key, site_id)``: the
global value under the bare ``key``, as before, and a Site's value under
``gtsettings:<site_id>:<key>``. A Site without a value of its own is cached
too, as "none", so the fallback to global costs no query; the global value is
read from its own entry, so changing it reaches every Site without its own
value. ``set_settings`` and any ORM save or delete of a ``GentelellaSettings``
(the admin included) clear the entry of that ``(key, site)``, and the one of
the ``(key, site)`` the row had before when the save changed its key or moved
it to another Site (or to global).
``clean_cache(keys, site=None)`` and the admin action *Clean settings cache*
clear it by hand, after a ``QuerySet.update()`` or a raw SQL change, which send
no signals.


Admin and UI
============

The admin of menus and settings shows the Site as an optional field (empty =
global), a column, and a filter by Site when ``django.contrib.sites`` is
installed. A ``CRUDView`` over ``MenuItem`` shows it as one more optional
field.


Demo
====

``python manage.py demomenu`` still creates the global demo menus.
``python manage.py demomenu --with-site`` also creates a second Site,
``127.0.0.1`` by default (``--site-domain`` changes it), with:

- an item of its own, *Site 2 home*;
- *Icons (site 2)*, which replaces the global *Icons* (same ``url_name`` and
  ``category``) with a single child;
- the setting ``sidebar_title`` = ``Demo site 2``.

Open the demo at ``http://localhost:8000/`` for the global menus and at
``http://127.0.0.1:8000/`` for those of the second Site.
