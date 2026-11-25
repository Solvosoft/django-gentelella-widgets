Designs
=======

``djgentelella.designs`` loads a **design document** -- the JSON
djgentelella-editor writes -- validates it and serves it as a page, live: no
code is generated and the editor does not need to be installed. A design goes
to production with one command::

    python manage.py gtdesigns_publish ventas/gtdesign/clientes.json

and is served at ``/designs/<path>`` inside the gentelella layout.

This module is the engine; the editor designs, previews and, when asked,
generates code on top of the same components. Components with data (tables,
charts, stats) come in their own modules; the ones here are structural.

Installation
------------

.. code:: bash

    pip install djgentelella[designs]

.. code:: python

    INSTALLED_APPS = [
        ...
        'django.contrib.sites',     # Page has an optional Site
        'djgentelella',
        'djgentelella.designs',     # app label: gtdesigns
    ]

then ``python manage.py migrate``. ``djgentelella.urls`` adds the pages and
the endpoints only when the app is installed.

The current Site is the one of :doc:`sites`
(``djgentelella.sites.get_current_site``): ``request.site`` when a middleware
such as ``CurrentSiteMiddleware`` set it, else the Site whose domain is the
request's host, else none -- and then only global pages are served.
``SITE_ID`` is not a fallback: a host without a Site of its own gets the
global pages. Keep ``SITE_ID = 1`` anyway, for Django's own views
(``LoginView``), which fail on a host that has no Site without it; add
``CurrentSiteMiddleware`` if ``SITE_ID`` should decide the Site.

The document
------------

The format is the editor's (``schema_version`` 1). ``djgentelella.designs.format``
owns it now: ``schema_v1.json`` is the envelope, :func:`upgrade` takes an older
document to the current version, :func:`validate_envelope` checks the shape.

.. code:: json

    {
      "schema_version": 1,
      "app": "ventas", "slug": "clientes", "kind": "page",
      "meta": {"title": "Clientes", "url": "clientes/", "url_name": "clientes",
               "permissions": {"view": ["ventas.view_cliente"]}},
      "assets": {"css": ".lead { color: #333 }", "js": ""},
      "forms": {"cliente": {"model": "ventas.Cliente", "fields": ["nombre", "pais"]}},
      "root": {"type": "page", "id": "page", "children": [
        {"type": "row", "id": "main", "children": [
          {"type": "col", "id": "body", "props": {"width": 12}, "children": [
            {"type": "html", "id": "intro", "props": {"html": "<p class=\"lead\">Hola</p>"}}
          ]}
        ]}
      ]}
    }

- ``meta.permissions`` -- ``{"view": [...]}``, or a plain list meaning the same
  -- are the permissions a user needs to see the page.
- ``assets.css`` is inlined in the page, cleaned; ``assets.js`` only when the
  publisher is trusted with it (see Security).
- Every form in ``forms`` is checked, used or not.
- Node ids are unique in the document; they appear in the markup as
  ``data-gtdesign="<id>"`` and in the endpoint URLs. The page's wrapper has
  its root's id there too, and the slug in ``data-gtdesign-page="<slug>"``,
  so a node whose id is the slug never makes a selector ambiguous.

When the format changes, ``format.CURRENT`` goes up and a function is added to
``format.UPGRADES``: ``{old_version: function(document) -> document}``. Every
entry point -- the engine, ``gtdesigns_publish`` -- upgrades first.

Errors are ``(path, message)`` tuples (``djgentelella.designs.jsonschema.Error``),
with JSON paths such as ``$.root.children[0].props.width``.

Components
----------

A node's ``type`` is a :class:`~djgentelella.designs.components.RuntimeComponent`:

==========  ==============  ==================================================
type        goes in         renders
==========  ==============  ==================================================
``page``    root only       ``<div class="gtdesign-page">``
``row``     page, col       ``<div class="row">``
``col``     row             ``<div class="col-md-<width>">`` (``col`` without)
``html``    col             its markup, cleaned (see Security)
==========  ==============  ==================================================

Writing one
"""""""""""

.. code:: python

    # ventas/gtdesigns.py
    from dataclasses import dataclass

    from django.utils.html import format_html

    from djgentelella.designs.components import NodeBuild, RuntimeComponent
    from djgentelella.designs.registry import register


    @dataclass
    class BannerBuild(NodeBuild):
        text: str = ''


    @register
    class Banner(RuntimeComponent):
        type = 'banner'
        label = 'Banner'
        icon = 'fa fa-bullhorn'
        parent_types = ('col',)
        props_schema = {'type': 'object', 'required': ['text'],
                        'additionalProperties': False,
                        'properties': {'text': {'type': 'string', 'minLength': 1}}}

        def resolve(self, node, rctx, path):
            return BannerBuild(node['id'], node['type'], node['props'],
                               text=node['props']['text'])

        def render(self, build, rctx, children):
            return format_html('<div class="alert alert-info">{}</div>', build.text)

        def media(self, build, rctx):
            return {'css': ['ventas/banner.css'], 'js': [], 'inline_js': ''}

- ``check_props`` validates ``node["props"]`` against ``props_schema`` (the
  ``x-widget`` hints there are for the editor).
- ``resolve(node, rctx, path)`` checks the node against the project and returns
  its **build**: a dataclass of data (model classes, field names), never code.
  Report problems with ``rctx.error(path, message)``.
- ``render(build, rctx, children)`` returns safe HTML; ``children`` is the
  rendered markup of the node's children.
- ``media()`` -- relative URLs go through ``static()``; duplicates are loaded
  once.
- ``endpoints(build)`` returns ``Endpoint(suffix, viewset, basename)``: see
  Endpoints.

``ResolveContext`` gives a component ``design``, ``request`` (``None`` while
validating offline), ``site``, ``user``, ``preview`` (querysets go empty, for
the editor), and ``model(label, path)``, ``form(key, path)`` and
``datasource(name, path)`` -- the last one needs ``djgentelella.datasources``.
Its hooks (``exposure``, ``check_permissions``, ``lookups``) are in "Extending
the engine".

Registering
"""""""""""

The registry is filled with the built-ins, then the ``gtdesigns.py`` module of
each installed app (imported from ``AppConfig.ready()``), then the dotted paths
of ``GT_DESIGN_COMPONENTS``. A repeated ``type`` replaces the previous one, so
a project can replace a built-in:

.. code:: python

    GT_DESIGN_COMPONENTS = ['miapp.components.MyHtml']

Exposing models
---------------

A design cannot use a model nobody exposed. Nothing is exposed by default:

.. code:: python

    # ventas/gtdesigns.py
    from djgentelella.designs.exposure import expose
    from ventas.models import Cliente, Pais

    expose(Cliente, exclude=('notas_internas',))
    expose(Pais, fields=['nombre'], perms={'view': ['ventas.view_pais']})

``fields``/``exclude`` limit the fields a design can name; ``perms`` sets the
permissions per action (``view``, ``add``, ``change``, ``delete``), by default
the model's own. A plain list applies to every action. ``exposed_models()``
lists them.

``rctx.model()`` refuses a model that is not exposed, and so does a form: its
model, the fields it names and the targets of its relations must all be
exposed, since a relation's choices list rows of the target.

Forms
-----

``forms[key]`` becomes a GTForm ModelForm (``rctx.form(key, path)`` returns its
``FormBuild``; ``build.form_class`` is the class, ``build.get_form()`` an
instance). The rules are the editor's: ``fields`` defaults to every editable
field the exposure allows; ``render`` is ``as_horizontal``, ``as_plain``,
``as_inline`` or ``as_grid`` with a ``grid`` placing every field once;
``widgets`` picks among ``djgentelella.forms.widgetmap.widget_choices`` --
autocompletes need a select2 lookup of the target in a ``gtselects.py``, tree
selects a ``TreeNode`` target. Without a choice, a relation with a lookup gets
the autocomplete. ``help`` texts become the fields' ``help_text``.

``djgentelella.designs.forms.default_form(model, fields=None)`` is the entry a
model gets by default -- ``{"model": "<app>.<Model>", "fields": [...]}`` with
every field a ModelForm would show (``is_form_field``), concrete fields first
and then the many-to-many ones, each with its default widget -- and ``fields``
(an exposure's names, say) keeps only those. djgentelella-editor imports a
model with it, and an application builder can write the ``forms`` of a new
``object_management`` with it.

Pages
-----

``Page`` (``djgentelella.designs.models``) holds the published document:
``site`` (optional), ``path``, ``title``, ``document``, ``schema_version``,
``hash`` (sha256 of the normalized document), ``is_published``,
``permissions``, ``created_at``/``updated_at``/``updated_by``.

``designs/<path:path>`` (URL name ``gt-design-page``) finds the page of the
current Site at that path, or else the global one (``site`` empty). A page
about one object (``meta.parent``) is at ``designs/<path>/<pk of the
object>``. Then:

- an unpublished page is a 404, except for users with
  ``gtdesigns.change_page``, who see it with a "preview" notice;
- the page's ``permissions`` and the document's ``meta.permissions`` are all
  required (403 otherwise);
- a signed-in user is required even without permissions, unless
  ``GT_DESIGNS_LOGIN_REQUIRED = False``.

The page extends ``gentelella/base.html``: the nodes go in ``content``, the
title in ``title``, CSS in ``extra_css`` and scripts in ``js``, each after
``block.super``. The resolution of a page is kept per process, keyed by its
``hash`` (``GT_DESIGNS_CACHE_SIZE``, 128 by default), so serving it does not
validate it again; a page whose document no longer resolves (a model withdrawn,
a component gone) is a 404, and editors see its errors. The cache keeps one
resolution per language: the errors and the labels of the builds are
translated.

Once a page is cached, serving it takes two queries before its components
read their data: the page with its publisher (``select_related('updated_by')``,
the document deferred and read only when the cache misses) and the page's
permissions. That count leaves out the current Site: when no middleware has
set ``request.site`` (``CurrentSiteMiddleware``), ``get_current_site`` looks it
up by the request's host, one more query per request. The session and the
signed-in user cost what they cost on any other view. The same holds for each request to a node endpoint. The
publisher's trust (below) is kept per process for ``GT_DESIGNS_TRUST_TTL``
seconds, keyed by ``(page.pk, page.updated_by_id, page.updated_at)``. A page
about one object (``meta.parent``) takes one more query, to find the page by
the path without the object's pk.

From Python: ``engine.resolve(document) -> (ResolvedPage, errors)``,
``engine.render(resolved, request)`` and ``engine.resolve_page(page)``;
``publishing.publish(document, site=None, path=None, user=None)``. ``publish``
and ``publishing.validate(document, user=None, site=None)`` resolve the
document for ``site`` (``engine.resolve(..., site=site)``, which a request
otherwise gives), so a ``flow:`` row link to a flow published only in that
Site is valid there. ``resolve_page`` resolves a page for its own Site in the
same way when it is served (a global page, without a Site), so what
``publish`` accepted for a Site is also what the page shows there.

**A page as data.** ``publishing.export_page(page)`` gives ``path``,
``title``, ``is_published``, ``document`` and ``permissions``
(``['app_label.codename', ...]``), with no pk and no Site.
``publishing.import_page(data, site=None, user=None) -> (page, errors)``
checks the shape (``validate_page_data``: unknown keys, types, the path, that
the permissions exist) and publishes the document with ``publish`` for that
Site, ``user`` as the publisher whose trust it gets; nothing is saved when
something is wrong. The page at ``(site, path)`` is replaced. The title and
permissions are the data's (without ``permissions``, those of
``meta.permissions``).

Endpoints
---------

A node can serve DRF viewsets at
``gtapis/designs/<page_id>/<node_id>/<suffix>`` (URL name
``gt-design-endpoint``). The router builds the routes from
``component.endpoints(build)`` with the build of the cached resolution, once
per resolution, and applies the page's own rules first (published, Site,
permissions). The Site rule holds for the pk too: the page of another Site is
not found, and neither is a global page when the current Site has a page of
its own at the same path -- the one ``designs/<path>`` would serve. The viewset finds what it serves on the request:
``request.gtdesign_page``, ``request.gtdesign_node`` and
``request.gtdesign_build``.

.. code:: python

    def endpoints(self, build):
        return [Endpoint('', RowsViewSet, 'rows-%s' % build.id),
                Endpoint('chart', ChartViewSet, 'chart-%s' % build.id)]

Conditions
----------

Any node -- of any component -- may carry a condition of
:doc:`authorization`, in ``props.condition`` or in ``meta.condition`` (one of
the two):

.. code:: json

    {"type": "row", "id": "finanzas",
     "meta": {"condition": {"any": [{"group": "Finanzas"},
                                    {"flag": "tablero_abierto"}]}},
     "children": []}

The engine handles it, so components do not have to:

* :func:`resolve` validates it (an unknown authorization is a publishing
  error, with its path, ``$.root.children[0].meta.condition.any[0]...``) and
  removes ``props.condition`` from the node the component checks and
  resolves, so a ``props_schema`` with ``additionalProperties: false`` needs
  no room for it. The resolution stays the same for every request; each
  ``ResolvedNode`` keeps its ``condition`` and its ``conditions`` (its own and
  its ancestors', root first).
* :func:`render` leaves out, per request, a node whose condition does not
  hold, with its children and their media.
* The endpoints of such a node -- or of a node under one -- answer 404:
  ``engine.node_endpoints(resolved, node_id, request)`` is ``None`` for them.
* A component that works on other nodes of the page names them with
  ``depends_on(build)`` (a list of node ids); the node then gets their
  conditions too, in ``ResolvedNode.requires``. The ``facets`` panel depends on
  its ``target``: hiding the table hides the panel and its counts.

This covers the components with data below: a hidden table, chart, stat,
classic CRUD or facets panel is not rendered -- a stat is not even computed --
and every route of its endpoint answers 404, on the page of one object as
well.

Data components
---------------

*(Componentes de datos.)* The components with data are built in
(``djgentelella.designs.data_components``). They port djgentelella-editor's
table, inline table, chart, stat and classic CRUD -- with the same validation
-- and add a facets panel, but they **serve** the node instead of generating
code: the serializers, filters and viewsets are made while serving from the
node's build (``djgentelella.designs.factories``).

==============================  ===============================================
type                            what it is
==============================  ===============================================
``object_management``           a DataTable with create, update, detail and
                                delete modals (``ObjectCRUD`` over an
                                ``AuthAllPermBaseObjectManagement``)
``inline_object_management``    the same over the children of the page's
                                parent object (``BaseInlineObjectManagement``)
``chart``                       Chart.js (``DJGraph``): one aggregate grouped by
                                a field or a date period
``stat``                        one number, optionally against the previous
                                period
``crud_classic``                djgentelella's ``CRUDView``: its list in the
                                page, its pages under the node's endpoint
``facets``                      a facets panel (``GTFacets``) filtering a table
``interactive_grid``            rows edited in place like a spreadsheet and
                                saved together (``djgentelella.designs.grid``)
``cards``, ``calendar``,        the rows of a data source as cards, on a
``map``                         calendar or on a map
                                (``djgentelella.designs.regions``, see "Region
                                components")
``tree``, ``timeline``,         the rows of a data source as a tree or on a
``metrics``                     timeline, and KPI cards against the previous
                                period
                                (``djgentelella.designs.tree_timeline_metrics``,
                                see "Tree, timeline and metrics")
==============================  ===============================================

.. code:: json

    {"type": "object_management", "id": "products",
     "props": {"model": "ventas.Producto", "form": "producto",
               "list_fields": ["nombre", "precio", "estado", "categoria"],
               "search_fields": ["nombre"],
               "perms": {"destroy": ["ventas.delete_producto",
                                     "ventas.supervisor"]},
               "row_links": [{"url_name": "categoria_productos",
                              "title": "Productos"}]}}

``object_management``
    ``model`` and ``form`` (a key of ``forms``, of the same model) are
    required. ``list_fields`` defaults to the first six fields of the form
    that are not long text or files; ``search_fields`` to its text columns
    (only text fields may be searched); ``ordering`` to ``["-pk"]``. ``perms``
    sets the permissions per action -- ``list``, ``retrieve``,
    ``detail_template``, ``get_values_for_update``, ``create``, ``update``,
    ``partial_update``, ``destroy`` -- over the exposure's (``view``, ``add``,
    ``change``, ``delete``); an empty list is refused, since
    ``AllPermissionByAction`` would deny everybody. The endpoint is
    ``gtapis/designs/<page>/<node>/`` with the routes of
    ``BaseObjectManagement`` (``<pk>/``, ``<pk>/get_values_for_update/``,
    ``detail_template/``). Columns filter like the editor's generated
    FilterSet (``icontains`` on text, ``exact`` on numbers, relations, booleans
    and choices, a range on dates, a CSV of pks on many-to-many); ``gtfilters``
    takes a JSON list of filters (``djgentelella.datasources``), which is
    how the facets reach the table. The page renders only the modals the user
    may use, and each row says which icons it gets.

``object_management`` in list mode
    ``datasource`` -- any registered data source, over a model of the project
    or not (one that reads an external API, say) -- instead of ``model`` and
    ``form``: a DataTable of its rows, **read only**, without create, update,
    detail or delete (``djgentelella.designs.source_tables``). ``list_fields``
    are columns of the source (by default its first six that are not JSON);
    ``search_fields`` its text columns among them; ``ordering`` (``[]``: by
    pk); ``perms`` only takes ``list`` (empty: only the source's own
    ``has_permission``); ``column_conditions`` hide columns as in a table;
    ``row_links`` need a source over a model of the project
    (``project_model``). ``form``, ``notify``, ``action_conditions`` and
    ``optimistic_lock`` are errors. A ``facets`` panel may target it: it reads
    the data source API, and the table gets its filters as ``gtfilters``. The
    endpoint answers the DataTables format (``?offset=&limit=&draw=&search=
    &ordering=&gtfilters=``), only over the columns the request sees: a filter
    on any other is a 400, an ordering by it is ignored. Remember that the
    source itself is still readable through ``gtapis/datasources/<name>/`` by
    whoever has its permission: a column a condition hides here is not a
    secret there. A source that cannot read now
    (``DataSourceUnavailable``) answers 503.

``row_links``
    Per row links to a page about one object: a URL name of the project that
    takes the pk (``args`` or ``pk``), a design page with ``meta.parent`` of
    the table's model -- by its ``meta.url_name`` or as ``page:<path>`` -- or
    a flow of :doc:`flows` over the table's model: ``flow:<name>`` opens its
    ``flow_detail`` and ``flow:<name>:<transition>`` the page that runs that
    transition (not an automatic one). A name without a dot is a flow of the
    design's ``app`` (``flow:review`` is ``ventas.review``), the way
    djgentelella-editor names the flows it designs. A design page must be
    published before the page that links to it; a flow must exist for the
    Site. Each link may carry a ``condition``: it only shows where it holds.

``column_conditions`` and ``action_conditions``
    Conditions inside a table (``object_management``,
    ``inline_object_management``) or a classic CRUD:

    .. code:: json

        "column_conditions": {"price": {"perm": "ventas.change_producto"}},
        "action_conditions": {"destroy": {"group": "Supervisores"}}

    A column whose condition does not hold is not shown, and the API leaves
    it out: not in the rows, the detail or its template, and the search, the
    filters, ``gtfilters``, the ordering -- the one the request asks and the
    default one (``ordering``, the model's ``Meta.ordering``; ``-pk`` when
    nothing else is left) -- and the facets of the table cannot use it. An
    update neither shows nor writes it: it leaves the update form and
    ``get_values_for_update``, and ``update``/``partial_update`` keep the
    row's value whatever the request sends. Creating a row still takes it --
    a new row reveals nothing; condition ``create`` to refuse it. An action whose condition
    does not hold has no button or row icon, and its routes answer 403. A
    table's actions are ``create``, ``update`` (with ``partial_update`` and
    ``get_values_for_update``), ``destroy`` and ``retrieve`` (with
    ``detail_template``); a classic CRUD's are its pages ``create``,
    ``detail``, ``update`` and ``delete``. The columns are those the component
    shows (a table's ``list_fields``, a CRUD's list and detail fields). The
    whole node -- ``list`` included -- goes with the node's own condition.
    Conditions are evaluated for the request and, on a page about one object,
    with that object when the component's API carries it (an inline table).
    See "Conditions with the object" below.

    **Per row.** In a table, the condition of ``update``, ``destroy`` or
    ``retrieve`` -- the actions on one row -- that names an authorization
    (``{"auth": ...}`` anywhere in it) is evaluated with each row instead, as
    the authorization's ``obj``:

    .. code:: json

        "action_conditions": {"update": {"auth": "es_dueno"},
                              "destroy": {"all": [{"perm": "ventas.delete_pedido"},
                                                  {"auth": "es_dueno"}]}}

    The page keeps the action's modal, each row of the API says in its
    ``actions`` whether it offers it, and the route of a row it does not hold
    for (``<pk>/``, ``<pk>/get_values_for_update/``, ``PUT``, ``PATCH``,
    ``DELETE``) answers 403 -- ``detail_template/`` has no row and is served.
    ``create`` and the conditions without an authorization are evaluated
    once, as above. ``designs.conditions.row_conditions(build)`` and
    ``row_denied(build, request, row)`` are the helpers.

    An inline table is not evaluated per row: on a page about one object all
    its conditions, those of ``update``, ``destroy`` and ``retrieve``
    included, get the object of the page (see "Conditions with the object"),
    so an authorization written for the parent keeps receiving the parent.

``optimistic_lock``
    ``true`` refuses to save a row somebody else changed after the update
    modal was filled: the API answers 409 and the modal offers to reload the
    form with the current data. ``false`` by default. See :doc:`locking`.

``optimistic_lock_required``
    An update that does not carry the version it read is refused too (428
    ``version_required``) instead of saving as before. ``false`` by default;
    ``true`` turns ``optimistic_lock`` on, and together with
    ``optimistic_lock: false`` is an error of the document.

``notify``
    Notifications when a row is created, updated or deleted through the table:
    ``{"on": "create|update|delete", "kind": "email|notice", "to": [...],
    "code", "subject", "message", "message_type"}``. Recipients are
    ``actor``, ``field:<path>`` (an allowed field of the row, through foreign
    keys) and, for emails, addresses or async_notification identifiers
    (``ventas@group.local``). An email goes through the async_notification
    ``EmailTemplate`` named ``code``, created from the design's texts the first
    time; a notice is a ``djgentelella.notification`` linking to the page.
    They are sent after the transaction commits, and a failure is logged, not
    raised. The texts see plain data only -- ``object`` (the allowed fields of
    the row, relations as text) and ``user`` (``username``, ``first_name``,
    ``last_name``, ``email``, ``full_name``) -- and may use template tags only
    when the publisher is trusted with templates.

``inline_object_management``
    Needs ``meta.parent`` (``{"model": "ventas.Categoria"}``) and
    ``parent_field``, a foreign key of ``model`` to that model, which the form
    must not include. The page is then served at ``designs/<path>/<parent pk>``
    (``designs/<path>`` alone is a 404), and needs the view permissions of the
    parent model; so does every request to the table, whose rows are only the
    parent's and whose new rows join it.

``chart``
    ``model`` (exposed) *or* ``datasource`` (a registered data source),
    ``group_by``, ``chart`` (``bar``, ``horizontal_bar``, ``line``, ``pie``,
    ``doughnut``), ``aggregate`` (``count``, ``sum``, ``avg``, ``min``,
    ``max``) of ``value_field`` (numeric), ``limit`` (10 groups). Grouping by
    a date takes a ``period`` (``day``, ``week``, ``month`` -- the default --,
    ``quarter``, ``year``) and leaves out the rows without a date. The build
    keeps ``group_by`` and ``period``, never an ORM expression; the rows come
    from ``djgentelella.datasources.query.aggregate``. ``perms`` defaults to
    the model's view permission, or for a data source its own permissions or
    the page's; the endpoint also asks the data source's ``has_permission``.

    ``facets`` (optional) is the id of a ``facets`` panel of the page: the
    chart follows it as the panel's table does. Each change of facet draws
    the chart again with the panel's filters, sent to its endpoint as
    ``gtfilters`` (the table's search box does not reach it). The panel has
    to filter the chart's rows -- a table over the chart's ``model`` (not an
    inline one, whose rows belong to one parent), or for a chart over a
    ``datasource`` a node whose ``facets_source`` is that data source -- and
    its columns must be columns of the chart. The endpoint takes filters only
    on the panel's columns, and not on one its table hides for the request
    (``column_conditions``): anything else is a 400, and so is ``gtfilters``
    on a chart without ``facets``.

    .. code:: json

        {"type": "chart", "id": "by_category", "props": {
            "model": "demoapp.Product", "group_by": "category",
            "facets": "product_facets"}}

``stat``
    The same measure without grouping, computed while the page renders (and
    at its endpoint). ``compare: {"field": <date>, "period": "month"}`` shows
    the current period's value and the change in percent from the previous one.

``crud_classic``
    ``model``, optional ``form`` (by default every field the exposure allows),
    ``list_fields``, ``search_fields``, ``views`` (``list``, ``create``,
    ``detail``, ``update``, ``delete``), ``perms`` per view and ``mode``:
    ``embed`` (the default) renders the ``CRUDView`` list inside the page,
    with its search (``?q=``) and pagination (``?page=``) on the page's own
    query string; ``link`` shows a tile opening it. Its pages are served at
    the node's endpoint: ``''``, ``create/``, ``<pk>/``, ``<pk>/update/``,
    ``<pk>/delete/``. ``optimistic_lock`` (``false`` by default) is
    ``CRUDView.optimistic_lock``: the update page refuses to save an object
    somebody else changed after it was opened. ``optimistic_lock_required``
    (which turns ``optimistic_lock`` on) is
    ``CRUDView.optimistic_lock_required``: a form posted without the version
    is refused. See :doc:`locking`.

``facets``
    ``target`` (the id of a table node of the page) and ``columns`` (fields
    of the table's model with a facet). The panel is djgentelella.datasources'
    ``GTFacets`` over the node's endpoint (``''`` describes the columns,
    ``facets/`` counts them): each count applies the other facets and the
    table's search, and each change reloads the table.

    The target may also be a node of another component that says it can be
    filtered (see "Facets over other components" below): the panel then reads
    that node's data source through the data source API.

**Preview.** ``engine.resolve(document, preview=True)`` -- the editor's
preview -- renders sample rows, sample charts and a sample stat, and every
viewset of a preview build has an empty queryset: nothing is read.

**Caching.** The classes are cached by ``(page hash, node id)`` and reused only
while the build is equal to the one they were made from, so a page published
again with another document, or a model exposed with other fields, gets new
ones.

**Security.** Every endpoint authenticates with the session and checks
``AllPermissionByAction`` with the build's permissions; only exposed models
and their allowed fields are accepted -- columns, searches, groups, facets,
the targets of relations shown, notification paths -- and a body that is not
a JSON object or a bad filter is a 400. The configuration reaches the browser
as JSON (``<script type="application/json">``), never as code, and the
renderers of ``gentelella/js/designs/data_components.js`` escape every value.

Interactive grid
----------------

*(Cuadrícula interactiva.)* ``interactive_grid``
(``djgentelella.designs.grid``) edits several rows of a model in place, each
cell with the djgentelella widget of its field, and saves them together: one
request, one transaction, every row or none.

.. code:: json

    {"type": "interactive_grid", "id": "prices",
     "props": {"model": "ventas.Producto",
               "columns": ["nombre", "precio", "estado", "categoria", "etiquetas"],
               "editable": ["precio", "estado", "categoria"],
               "widgets": {"estado": "RadioHorizontalSelect"},
               "actions": ["update"],
               "edit_conditions": {"precio": {"perm": "ventas.cambiar_precio"}},
               "action_conditions": {"update": {"auth": "es_dueno"}},
               "page_size": 25}}

Props:

``model`` *or* ``datasource``
    An exposed model, or a registered ``ModelDataSource`` over one: then the
    rows are those of the data source's queryset (its permissions, Site rule
    and filters apply, to reading and to writing: a row outside it is a 404),
    and the columns must be fields it offers. The model must be exposed too.

    Any other data source (a ``FunctionDataSource``, one whose rows come from
    an external API...) makes a **read-only** grid: ``columns`` are columns of
    the source (not JSON), there are no ``editable`` columns, ``actions``,
    ``widgets``, ``edit_conditions`` or ``action_conditions`` (each one an
    error), ``perms`` only takes ``list`` (empty: only the source's own
    check) and the locking props are ignored. The page has no *Add row* or
    *Save changes*; its endpoint answers ``{"data", "count"}`` like the
    editable grid's list, every row with ``actions`` false and relations as
    ``{id, text}``, and ``search`` only over its ``search_fields`` that the
    request sees. ``grid_page_context`` serves both kinds.
``columns`` (required)
    Fields of the model the exposure allows; not files, JSON, binary or
    points. A column that does not exist is an error of the document.
``editable``
    The columns a cell edits; by default every column it can edit. Not the
    primary key, ``editable=False`` fields, many-to-many relations (shown
    read-only), files, JSON, binary or points.
``widgets``
    The widget of an editable column, with the rules of the design's
    ``forms`` (``djgentelella.forms.widgetmap``): an autocomplete needs a
    lookup in a ``gtselects.py``, a tree select a tree model.
``actions``
    What the grid offers: ``create``, ``update``, ``destroy`` (all by default).
    ``create`` needs every required field of the model among ``editable``.
``perms``
    ``list``, ``create``, ``update``, ``destroy``; by default the exposure's
    ``view``, ``add``, ``change``, ``delete``.
``column_conditions``, ``edit_conditions``, ``action_conditions``
    As in a table. ``column_conditions`` hides a column (not in the rows, the
    search or the ordering; writing it is a 403). ``edit_conditions`` keeps
    the column but shows it read-only where the condition does not hold, and
    writing it there is a 403. ``action_conditions`` takes ``create``,
    ``update`` and ``destroy``. A condition that names an authorization
    (``auth``) is evaluated **with each row**: on ``update``/``destroy`` it
    says whether that row can be changed or deleted, on a column whether that
    cell can be edited (a new row is evaluated with ``obj=None``).
``optimistic_lock``
    ``true`` by default: every update and delete must carry the ``_version``
    of the row it read (:doc:`locking`). ``false`` saves over whatever is
    there. ``optimistic_lock_required`` is accepted for the same contract as
    the tables: a grid with locking already refuses a row without its version
    (428), and ``true`` with ``optimistic_lock: false`` is an error.
``search_fields``, ``ordering``, ``page_size``, ``title``
    As in a table; ``ordering`` is ``["pk"]`` by default and ``page_size``
    25 (at most 200).

**In the page** a row starts as text. Clicking a cell (or the pencil) edits
its row: each editable cell gets the widget of the column, booted like a modal
form's. The row is marked as changed as soon as a value differs from what it
read; *Add row* appends a new row, the trash marks a row to be deleted when
saving, and the undo icon drops the changes of its row. Nothing is written
until *Save changes*. Paging and searching wait until there is nothing
pending.

**The API** of the node (``gtapis/designs/<page>/<node>/``):

``GET ''``
    ``{"data": [...], "count": n}``, with ``limit``/``offset``, ``search``,
    ``ordering`` and ``gtfilters`` as in a table. Each row has its columns
    (relations as ``{id, text}``), its ``_version``, what the request may do
    on it (``"actions": {"update": true, "destroy": false}``) and which of its
    editable cells are read-only (``"readonly": ["price"]``).
``GET <pk>/``
    One row again, the same shape, with its ``ETag``: what the browser reads
    to reload a row after a conflict.
``POST save/``
    A batch:

    .. code:: json

        {"rows": [
          {"key": "r1", "op": "update", "id": 5, "_version": "…", "data": {"precio": "3.10"}},
          {"key": "n1", "op": "create", "data": {"nombre": "Pera", "precio": "1.00"}},
          {"key": "r7", "op": "delete", "id": 7, "_version": "…"}
        ]}

    ``key`` names the row in the answer (the browser's own key); an update
    sends only the fields it changes. At most 500 rows.

Every row is checked before anything is written, in the order of
:doc:`locking`:

1. **403** ``permission_denied``: the user lacks the permission of the
   action, the grid does not offer it, its condition does not hold (for the
   grid, then for that row), or the row writes a column it cannot
   (``fields`` lists them);
2. **404** ``not_found``: the row does not exist, or the grid does not reach
   it;
3. **409** ``version_conflict`` (with the current ``version``), or **428**
   ``version_required`` without a ``_version``;
4. **400** ``invalid``: the validation of the data, as ``errors`` by field.

If every row passes, they are written in that same transaction -- deletes,
then updates, then new rows -- and the answer is **200**:

.. code:: json

    {"saved": true, "rows": [
      {"key": "r1", "op": "update", "id": 5, "row": {"id": 5, "_version": "…", "…": "…"}},
      {"key": "n1", "op": "create", "id": 12, "row": {"…": "…"}},
      {"key": "r7", "op": "delete", "id": 7}]}

If any row fails **nothing is saved**, and the answer has the status of the
first kind of failure in the order above (403, then 404, 409, 428, 400) and
lists each failed row:

.. code:: json

    {"saved": false, "code": "batch_rejected",
     "detail": "Nothing was saved: 2 of 3 rows have problems.",
     "rows": [
       {"key": "r1", "op": "update", "id": 5, "status": 409,
        "code": "version_conflict", "detail": "…", "version": "…"},
       {"key": "n1", "op": "create", "status": 400, "code": "invalid",
        "detail": "…", "errors": {"precio": ["A valid number is required."]}}]}

A body that is not a batch is a 400 with ``"code": "invalid_batch"``; a
database error while writing (two new rows with the same unique value) a 400
``batch_rejected`` with no rows. The browser shows field errors under their
cell and the rest next to the row; a conflict offers to **reload that row**
(``GET <pk>/``), which drops its changes and keeps those of the other rows.

**Cost.** The rows a batch updates or deletes are read -- and locked with
``select_for_update`` -- in one query, ordered by pk; each relation the rows
set is read once for all of them. When the model has no ``save()`` of its own
and nothing listens to its ``pre_save``/``post_save``, the updates are one
``bulk_update`` (its ``auto_now`` fields are set as ``save()`` would) and the
new rows one ``bulk_create`` (when the database returns their keys); the
deletes are one ``delete()`` of a queryset unless the model has its own
``delete()``. Otherwise each row is saved with ``save()``. A unique field
adds its validation query per row. ``tests/InteractiveGrid_Test.py`` pins
the number of queries: the same for one row and for many.

Flow kanban
-----------

*(Tablero Kanban por estado de flujo.)* ``flow_kanban``
(``djgentelella.designs.flow_kanban``) shows the objects of a flow of
:doc:`flows` as cards, one column per state. Moving a card -- dragging it, or
with its **Move to** menu, which works without a mouse -- runs a transition of
the flow: the board never changes a state by itself.

.. code:: json

    {"type": "flow_kanban", "id": "tickets", "props": {
        "flow": "demoapp.TicketFlow",
        "states": ["queued", "in_progress", "waiting", "resolved", "closed"],
        "title_field": "subject",
        "fields": ["priority", "created_at"],
        "ordering": ["-pk"],
        "limit": 5,
        "page_size": 10}}

``flow`` (required)
    The flow's name. A name without a dot is one of the design's ``app``, as
    for the ``flow:`` row links. Its model must be exposed (`Exposing
    models`_).
``states``
    The columns and their order. By default every activity of the flow an
    object can wait in: states, human tasks, waits, parallels and subflows --
    not switches, automatic actions nor joins, which an object leaves at once.
``title_field``, ``fields``
    The card's title (``str(object)`` by default) and the fields shown under
    it: fields the exposure allows, not many-to-many, JSON nor files. A
    relation is read with the cards (``select_related``) and its model must be
    exposed too. A choice shows its label.
``ordering``
    The order of the cards in a column: allowed fields, ``pk`` or
    ``flow_due_at``; ``-pk`` by default. The pk is added last, so the pages of
    a column never overlap.
``limit``
    A **visual** limit per column: past it the column's counter turns red.
    Nothing refuses a move because of it (no strict WIP).
``page_size``
    Cards per column on load and on each **Load more** (20, at most 100).
``site_field``
    A foreign key of the model to ``sites.Site``: only the objects of the
    current Site and the global ones (``NULL``) are shown.

A flow, a state or a field that does not exist is an error of the document:
it does not publish, as any other component.

**What it shows.** Only what ``Flow.get_queryset(user)`` lets the user reach
(:doc:`flows`, "Authorization"), of the current Site: an object whose flow
instance belongs to another Site is left out, and so are, with
``site_field``, the objects of another Site. The flow itself is looked up for
the Site of each request (``get_flow(name, site=...)``), as the flow pages
do. Each card links to ``flow_detail``. An instance suspended, terminated or
in error shows its status and cannot be dragged.

**Moving a card.** When a drag starts, the columns the card may go to are
marked: those a non-automatic transition from its state reaches, for which
the user holds the permissions. Conditions need the object, so they are
checked on the drop, when the browser asks the node's endpoint for the
transitions between both columns for that object and user:

* none: the card goes back to its column and the board says why (the
  condition's reason, the permission, "no transition goes from A to B");
* one: it runs; a transition with a ``form`` opens it in a modal, with a
  comment box;
* several: the user picks one.

The transition runs with ``Flow.run`` -- the permission and the condition are
checked again on the locked object, the form is applied, the actions run and
``FlowTransitionLog`` gets the row, or nothing at all. Any refusal (permission,
condition, an invalid form, somebody else moved it first) puts the card back
with the message. After the run the card lands where the object really is:
automatic transitions may take it further, or off the board.

**Its endpoint** (``gtapis/designs/<page>/<node>/``, session authentication
with CSRF, JSON):

* ``GET cards/?state=<s>&offset=<n>`` -- the next cards of a column, as HTML
  rendered and escaped by the server, and ``has_more``;
* ``GET <pk>/transitions/?target=<s>`` -- ``transitions`` the user may run
  now (``name``, ``label``, ``form``, ``css_class``), ``refused`` with their
  ``reason``, and a ``detail`` when there is none;
* ``GET <pk>/form/?transition=<t>`` -- the modal's form;
* ``POST <pk>/move/`` with ``transition``, the form's fields (prefix
  ``flow``) and ``flow_comment-comment`` -- 200 with the new ``state``,
  ``state_label``, ``status``, ``error`` and the new ``card`` (``null`` when
  it left the board); 400 with ``errors`` and the form again; 403 with
  ``detail`` when the flow refuses it; 404 for an object outside the board, a
  state that is not a column, or a transition that is automatic or goes to a
  state the board does not show.

**Cost.** Rendering the board takes two queries whatever the number of cards:
the count of each column, and the first page of every column at once (a
window function numbering the cards per state). Then come the flow's own
lookups (its ``FlowDefinition``, the user's permissions), once per request.

The JavaScript is ``gentelella/js/designs/flow_kanban.js`` (HTML5 drag and
drop, no library) and the styles ``gentelella/css/flow_kanban.css``; the
configuration reaches the browser as JSON. A transition between two states
the board shows is reachable by dragging; one that stays in its state
(``escalate`` in the help desk demo) is not, use the flow's pages for it. The
demo publishes the help desk board at ``/designs/tickets-board/``.

Grid and Kanban outside a page
------------------------------

Code generated from a design (djgentelella-editor) or an application builder
serves a grid or a board with djgentelella's own viewsets and templates, but
without a published ``Page``. The names it uses are public (``__all__``):

``designs.grid``
    ``GridState`` (what a request may see and do), ``required_fields(model)``,
    ``NOT_SHOWN`` and ``NOT_EDITABLE`` (the kinds of field a grid cannot show
    or edit), ``grid_viewset_for(build)``, ``grid_columns``, ``grid_config``
    and ``TEMPLATE``.
``designs.flow_kanban``
    ``board``, ``card``, ``render_cards``, ``resting_states(flow)``,
    ``moves_for``, ``kanban_flow``, ``kanban_config``, ``kanban_messages``,
    ``FlowKanbanViewSet`` and ``TEMPLATE``.

The context of each template comes from a build, the request and the URL of
its endpoint -- what the components render with too:

.. code:: python

    from django.template.loader import render_to_string
    from djgentelella.designs import flow_kanban, grid

    context = grid.grid_page_context(PRICES_GRID, request, reverse('prices-api'),
                                     form_class=PricesForm, columns=COLUMNS)
    html = render_to_string(grid.TEMPLATE, context, request=request) \
        if context is not None else ''

    context = flow_kanban.kanban_page_context(TICKETS, request, reverse('tickets-api'))

``grid_page_context(build, request, url, *, form_class=None, columns=None)``
    ``{'b', 'cells', 'allowed', 'config'}``: the cells the request may edit,
    what it may do and the ``data-gtconfig`` JSON of interactive_grid.js.
    ``form_class`` replaces ``build.form`` (a generated build has none);
    ``columns`` are the columns of the build already described
    (``name``, ``title``, ``kind``, ``widget``...): the hidden ones are left
    out and ``editable`` is set for the request. ``None`` when the request
    may not see the grid -- without the ``list`` permissions or the data
    source's.
``kanban_page_context(build, request, url)``
    ``{'b', 'columns', 'config'}``: the columns with their first cards and
    the JSON of flow_kanban.js. ``None`` without an authenticated user, a
    flow for the request's Site or one of the columns in that version.

``FlowKanbanViewSet`` serves the build its ``get_build()`` answers: the
class attribute ``kanban_build`` when a subclass sets it, otherwise
``request.gtdesign_build`` (what the design endpoint sets); without either it
is a 404. The grid's viewset (``grid_viewset_for(build)``) already carries
its build.

The same goes for the regions, the read-only tables and the facets panels
over a data source (``designs.regions``, ``designs.source_tables``,
``designs.data_components``):

.. code:: python

    from djgentelella.designs import data_components, regions, source_tables

    class MeetupCardsApi(regions.CardsViewSet):
        region_build = MEETUP_CARDS            # no initial() needed

    context = regions.region_page_context(MEETUP_CARDS, request,
                                          reverse('meetup-cards-api'))
    html = render_to_string(context['template'], context, request=request) \
        if context is not None else ''

    context = data_components.facets_page_context(MEETUP_FILTERS, request)
    # render_to_string(context['template'], context) -> the panel

``region_page_context(build, request, url, *, component=None)``
    ``{'b', 'preview', 'template', 'config'}``: the template of the
    component (``gtdesigns/components/cards.html``...) and its
    ``data-gtconfig`` JSON -- ``id``, ``type``, ``url``, with a
    ``datasource`` its ``datasource_url`` and ``group`` (the facets it
    follows, ``filtered_by`` included), and what the component adds
    (``config(build, rctx)``: page size, FullCalendar and its locale,
    markercluster, centre...). ``component`` is the registered one of
    ``build.type`` by default. ``None`` when the request may not see it.
``facets_page_context(build, request, datasource_url=None)``
    ``{'b', 'preview', 'template', 'url', 'group', 'columns'}`` of a facets
    panel over a data source (its target is a region, a chart or a list in
    list mode): ``url`` is the data source API (``gtdatasource``) unless
    ``datasource_url`` says otherwise, ``group`` is ``gtdesign:<target>``.
    ``None`` without ``build.perms`` or the source's ``has_permission``. A
    panel over a table of a model has an endpoint of its page:
    ``ValueError``. With it, a page that uses ``filtered_by`` or the
    ``facets`` prop of ``chart`` can be generated too.

``table_page_context(build, request, url)`` (``designs.data_components``)
    ``{'b', 'template', 'forms', 'base', 'modal_ids', 'allowed', 'config'}``
    of ``object_management`` in list mode: the DataTable over a
    ``SourceTableViewSet`` at ``url``, with the columns the request sees and
    the row links (``row_link_config``, public too). Render it with
    ``request=request``. ``None`` as ``grid_page_context``; ``ValueError``
    for a table with a form.

Whether a grid over a ``datasource`` is read only is the source's call
(``grid.grid_can_edit(source)``: a ``ModelDataSource`` over a model of the
project edits), not whether the build has a ``form``: a generated build
without one, over such a source, is still the editable grid that
``grid_page_context(..., form_class=...)`` draws.

``RegionMixin`` (the base of ``CardsViewSet``, ``CalendarViewSet`` and
``MapViewSet``) and ``SourceRowsMixin`` (``SourceTableViewSet``,
``SourceGridViewSet``) serve the build ``get_build()`` answers: the class
attribute ``region_build`` when a subclass sets it, otherwise
``request.gtdesign_build``; without either, 404 -- as ``kanban_build``.

**The 403 of a region.** ``check_access(build, request)`` is the rule every
region endpoint applies: all of ``build.perms``, then
``region_source(build).has_permission(request)`` (403), and 404 when the
data source is gone. ``region_page_context`` applies the same one to the
page. ``check_access``, ``read_rows``, ``request_params`` and
``region_queryset`` are public (``__all__``).

A build's ``page_hash`` is only the key the factories cache their classes by,
with the node id: nothing checks it against a document. A build written as
code may set any stable string -- djgentelella-editor sets
``'<app>.<slug>'`` -- as long as two different builds of one node id never
share it in one process.

Region components
-----------------

*(Componentes de región: tarjetas, calendario y mapa.)* ``cards``,
``calendar`` and ``map`` (``djgentelella.designs.regions``) show the rows of a
data source (:doc:`datasources`) -- or of an exposed model -- as cards, as
events of a calendar or as points of a map. The three share one contract:

``datasource``
    a registered data source: its ``get_queryset(request)`` (Site and
    permissions) is every row the component shows, and its
    ``has_permission(request)`` answers 403 for the others. Or ``model``, an
    exposed model, with an optional ``site_field`` (a foreign key to
    ``sites.Site``: the current Site's rows and the global ones); its rows are
    those of a ``ModelDataSource`` over the fields its exposure allows, and
    seeing them needs ``perms`` (the model's view permission by default).
``title_field``, ``subtitle_field``, ``fields``
    columns of the data source: the title, the subtitle and more fields shown
    (on the card, in the event, in the popup). Relations show their text and
    choices their label.
role columns
    ``image_field`` (cards: a file field or a URL), ``start_field`` and
    ``end_field`` (calendar: a date or a date-time; the end is optional),
    ``color_field`` (calendar), ``point_field`` (map: a
    :doc:`GTPointField <widgets/maps>`, ``"lat,lng"``).
``row_links``
    as a table's: a URL name taking the pk, ``page:<path>`` or ``flow:<name>``,
    each with its ``condition``. The first one the user may see is the row's
    own link: the card title, a click on the event, the link of the popup.
``column_conditions``
    ``{field: condition}``: a field of ``fields`` (or the subtitle) shown only
    when it holds; the endpoint refuses a filter or an ordering over it (400).
``ordering``, ``perms``, ``title``
    as in the other components. A node condition (``props.condition``) hides
    the component and its endpoint (404).

.. code:: json

    {"type": "cards", "id": "meetup_cards",
     "props": {"datasource": "demoapp.meetups", "title_field": "title",
               "subtitle_field": "city", "image_field": "picture",
               "fields": ["kind", "starts_at"], "page_size": 6,
               "row_links": [{"url_name": "admin:demoapp_meetup_change",
                              "title": "Open"}]}}

    {"type": "calendar", "id": "meetup_calendar",
     "props": {"datasource": "demoapp.meetups", "title_field": "title",
               "start_field": "starts_at", "end_field": "ends_at",
               "color_field": "kind",
               "colors": {"talk": "#3498db", "workshop": "#e67e22"},
               "filtered_by": "filters"}}

    {"type": "map", "id": "meetup_map",
     "props": {"datasource": "demoapp.meetups", "title_field": "title",
               "point_field": "location", "fields": ["kind"], "cluster": true,
               "filtered_by": "filters"}}

**Cards** (``page_size``, ``per_row``, ``search``). The endpoint *is* a
``ListAreaViewset`` (``views/listAreaViewset.py``) and the browser reads it
with ``CardList`` (``api_list.js``), the same pair the hand-written card
lists use: ``?page=&page_size=&params=`` answers ``data``, ``recordsTotal``,
``totalPages``, ``currentPage`` and the Squirrelly ``template`` that draws
them, escaping every value. ``ListAreaViewset`` gained
``get_template_context()`` and ``template_response()`` for that, and works
without a ``filter_form``; its answer did not change. A page of cards takes
the same queries for one card or a hundred: the count, the pks of the page and
their rows (plus one per relation shown).

**Calendar** (``initial_view``, ``limit``, ``colors``, ``color_rules``).
FullCalendar asks for the **visible range only**: ``?start=&end=`` (ISO dates,
at most 400 days apart, 400 otherwise), and the endpoint reads the rows that
overlap it -- start before the end, and end after the start (or, without an
end, start inside) -- in one query, at most ``limit`` (500; ``truncated``
says when there were more). The colour of an event is the first
``color_rules`` item whose filter (a filter of the parameter document)
matches, else ``colors[<value of color_field>]``, else the value itself when
it is a colour. An event of a date column is an all-day one.

The calendar speaks the language of the page: ``locale`` is the request's
``LANGUAGE_CODE`` (or the active language), and on a page that is not in
English the script also loads FullCalendar's locales
(``vendors/fullcalendar/locales-all.global.min.js``, ~26 KB, downloaded by
``loaddevstatic``). FullCalendar falls back from ``pt-br`` to ``pt``, and to
English for a language it does not know.

**Map** (``cluster``, ``bbox``, ``limit``, ``center``, ``zoom``, ``height``).
The endpoint is a ``BaseMapView`` (``views/maps.py``), so its payload is the
one ``DJMap`` and ``maplib.js`` draw. It sends at most ``limit`` points (500,
``truncated`` when there were more). With ``bbox`` (the default), after the
first load the browser asks again for the points of the visible box when the
map moves: ``?bbox=<west>,<south>,<east>,<north>``, filtered in the database
(the ``"lat,lng"`` text is split and cast inside a ``CASE`` that skips a value
that is not a point, so PostgreSQL never fails on one), across the
antimeridian too. The popup is HTML rendered and escaped by the server.

*What the box costs.* The point is text, so no index helps: the database
splits and casts the ``"lat,lng"`` of **every row** the source's queryset
(with the panel's filters) holds, and stops at ``limit + 1`` matches. That is
cheap for the few thousand rows a map shows, and grows with the table: with
tens of thousands of points, narrow the source (its filters, the Site rule)
or keep the coordinates in two float columns behind a source of your own. An
expression index only helps if it repeats, character for character, the SQL
``regions.point_coordinates`` generates, which is not a stable interface, so
djgentelella does not ship one. A prefilter on the text cannot work either
(``"10.5"`` sorts before ``"9.9"``, and ``"-"`` before both), so there is
none.

**Point columns.** The columns of a ``ModelDataSource`` over a
``GTPointField`` carry ``extra={'point': True}`` (also in the API's
``columns``), so a designer can offer them as the ``point_field`` of a map
without resolving the field.

**Facets.** A ``facets`` panel may name a region node over a ``datasource``
as its ``target``; the panel and the component share the data source state of
the page (``gtdesign:<target>``), and the component reloads with the panel's
filters and search as the parameter document (``?params=``), which its
endpoint applies with ``apply_params`` on top of ``get_queryset(request)``. A
component that is not the target follows the same panel with
``filtered_by: <panel id>``, over the same data source: one panel then filters
the cards, the calendar and the map. A region over a ``model`` cannot be a
facets target (the panel reads a registered data source).

FullCalendar and Leaflet.markercluster are loaded by the component's script
(``gentelella/js/designs/regions.js``) when the page does not bring them
(``use_readonlywidgets`` and ``use_maps``); Leaflet itself is always there.
The demo publishes the three over ``demoapp.meetups`` at
``/designs/meetups/``.

Tree, timeline and metrics
""""""""""""""""""""""""""

*(Árbol, línea de tiempo y tarjetas de métricas.)* ``tree``, ``timeline`` and
``metrics`` (``djgentelella.designs.tree_timeline_metrics``) are region
components too: they take ``datasource`` (or ``model`` with ``site_field``),
``title``, ``filtered_by`` and ``perms`` as above -- ``tree`` and ``timeline``
also ``title_field``, ``subtitle_field``, ``fields``, ``row_links``,
``column_conditions`` and ``ordering`` -- read only ``get_queryset(request)``
of the source through ``apply_params``, follow the facets of the page and
answer 403 without the build's or the source's permissions, 404 under a false
node condition and 503 when the source raises ``DataSourceUnavailable``. No
library is needed: ``gentelella/js/designs/tree_timeline_metrics.js`` and
``gentelella/css/tree_timeline_metrics.css`` come with the components'
``media``.

.. code:: json

    {"type": "tree", "id": "org_tree",
     "props": {"datasource": "demoapp.departments", "title_field": "name",
               "subtitle_field": "head", "parent_field": "parent",
               "icon_field": "icon", "load": "lazy", "ordering": ["name"],
               "row_links": [{"url_name": "admin:demoapp_department_change",
                              "title": "Open"}]}}

    {"type": "timeline", "id": "meetup_timeline",
     "props": {"datasource": "demoapp.meetups", "title_field": "title",
               "start_field": "starts_at", "end_field": "ends_at",
               "description_field": "city", "color_field": "kind",
               "colors": {"talk": "#3498db", "workshop": "#e67e22"},
               "page_size": 5}}

    {"type": "metrics", "id": "purchase_metrics",
     "props": {"datasource": "demoapp.purchases", "date_field": "created_at",
               "period": "month",
               "metrics": [
                 {"label": "Requested", "fn": "sum", "column": "amount",
                  "format": "currency", "prefix": "$",
                  "higher_is_better": false},
                 {"label": "From ACME", "fn": "count",
                  "filters": [{"column": "supplier", "op": "eq",
                               "value": "ACME"}]}]}}

**Tree** (``parent_field``, ``id_field``, ``icon_field``, ``load``,
``limit``, ``expand``). ``parent_field`` names each row's parent: a foreign
key to the same model, or a column holding the ``id_field`` of the parent
(``id_field`` is the primary key when empty, and must then be of the same
kind). ``icon_field`` gives a CSS class (``fa fa-folder``); anything else is
dropped. With ``load: "lazy"`` (the default) the browser asks for one level
at a time, ``?parent=<id>&offset=<n>``, at most ``limit`` rows (200) per
request with a "More" button after them; ``{"nodes", "next_offset",
"orphans", "cycles", "checked"}`` -- each node ``{key, title, subtitle,
fields, icon, url, links, children, orphan, cycle}``. A level costs a constant
number of queries: its page of pks, their rows, which of them have children,
and for the roots one more for the ``(id, parent)`` pairs (at most 20 000; a
larger source is not checked for cycles and ``checked`` says so). With
``load: "full"`` it reads at most ``limit`` rows at once and answers them as a
**flat list in pre-order**, each with its ``parent`` and ``depth``; ``expand``
levels start open.

A row whose parent is not among the rows -- deleted, of another Site,
filtered out by a facet, or beyond the limit -- is shown at the root marked
``orphan``. The rows of a cycle (``A → B → A``, or a row that is its own
parent) are reachable from no root: the smallest id of each cycle is shown at
the root marked ``cycle``. Nothing is walked recursively, a row is never its
own child, and the browser never opens a node that is already one of its
ancestors, so neither hangs the page; a note above the tree says how many
there are.

**Timeline** (``start_field``, ``end_field``, ``description_field``,
``color_field``, ``colors``, ``color_rules``, ``page_size``). Newest first:
``?cursor=&from=&to=&params=`` answers ``{"items", "next"}``, at most
``page_size`` items (20) starting in ``[from, to)`` when given, and ``next``
is the cursor of the page before (``None`` at the oldest). The cursor is the
``(start, pk)`` of the last item shown (keyset paging), so the hundredth page
costs the queries of the first and no row is skipped or repeated when several
share a start. Each item: ``{id, title, subtitle, description, fields, start,
end, when, until, group, color, url, links}``; ``group`` is the month it is
listed under. The colour is chosen like the calendar's.

**Metrics** (``metrics``, ``date_field``, ``period``, ``to_date``,
``per_row``). Each card of ``metrics`` (1 to 12) is ``{label, fn, column,
filters, format, decimals, prefix, suffix, icon, compare, higher_is_better,
condition}``: an aggregate of the parameter document (``count`` -- without a
column, the rows --, ``count_distinct``, ``sum``, ``avg``, ``min``, ``max``;
the last four over a numeric column) of the rows matching its ``filters``
(filters of the parameter document), shown as a ``number``, ``currency``
(``prefix``/``suffix``) or ``percent`` (the value is a ratio: 0.25 is 25 %),
with ``decimals`` (0 for counts, 2 otherwise). Its ``condition`` hides it.

With ``date_field`` (a date or date-time column) and ``period`` (``day``,
``week``, ``month``, ``quarter``, ``year``) every card shows the **current**
period, and a card with ``compare`` (the default) also the change against the
**previous** one: absolute (``+10.00``) and in percent (``+50.0 %``), an
arrow, and green or red after ``higher_is_better`` (``false`` for costs). The
previous period is the whole of it; with ``to_date`` only as far into it as
today is into the current one (the first ten days of last month on the 10th).
A count or a sum of no rows is 0 and an average, minimum or maximum of none is
``—``; when the previous period is empty or zero there is no percentage (no
division by zero), and with nothing to compare the card says so.

Every card is computed in **one** aggregate query (conditional aggregates,
``Sum(..., filter=Q(...))``) over the rows of the source after the page's
facets. The page renders the cards on the server; the endpoint, ``?params=``,
answers ``{"metrics": [card], "html"}`` -- the same cards rendered by the
same template -- and the browser swaps them when a facet changes. A source
that is down leaves the page up: the cards say they could not be computed.

The demo publishes the three at ``/designs/insights/``: an organization chart
(``demoapp.departments``), the meetups on a timeline with a facets panel, and
two rows of cards over the meetups and the purchase requests.

Extending the engine
--------------------

Whoever resolves designs another way -- djgentelella-editor, an application
builder -- does it through these hooks instead of the engine's private
functions.

**The context.** Every component asks the :class:`ResolveContext` what the
design may use; a subclass that answers otherwise changes them all:

``exposure(label, path=None)``
    the ``Exposure`` of a model, or ``None`` after reporting why it
    cannot be used. ``path=None`` only asks, reporting nothing. Forms, tables,
    charts, facets and the notifications (their model and their ``field:``
    paths) all go through it.
``check_permissions(path, perms)``
    reports the ``app.codename`` permissions that do not exist, and an empty
    list. By default they are read from ``auth_permission``; djgentelella-editor
    reads them from the models' ``Meta``, before ``migrate``. The engine asks
    it for ``meta.permissions`` (when there are some) and every component for
    its ``perms``.
``lookups(model)``
    the select2 lookups (basenames) a design may use for a model, the first one
    preferred: the autocomplete widgets of its forms and the filters of a
    table's relation columns. By default those registered in ``gtselects.py``.
``component(type)``
    the component of a type the design is resolved with.
``flow(name, path=None)``
    the :doc:`flows` flow ``name`` for the design's Site, or ``None``
    (reporting why at ``path`` when one is given). Every flow a design names
    goes through it: the ``flow`` of a ``flow_kanban`` and the ``flow:`` row
    links. By default the flows registered in Python and the published
    ``FlowDefinition`` of the Site (``get_flow(name, site=...)``), with a
    name without a dot read as one of the design's ``app``. A subclass can
    answer flows that are not published yet -- djgentelella-editor builds
    them from the flow designs of the app -- to validate a board without the
    database, and call ``super()`` for the rest.
``row_link(link, model, path)``
    the ``RowLink`` of one item of a table's ``row_links`` (its ``condition``
    already validated) for rows of ``model``, or ``None`` after
    ``self.error(path, ...)``. By default
    ``data_components.resolve_row_link``: a URL name, a published design page
    or a flow. djgentelella-editor can link the pages and flows it generates
    next to the design, and call ``super()`` for the rest.

``data_components.parse_flow_link(text, known=None)`` reads a
``flow:<name>[:<transition>]`` link without a context: ``(name,
transition)`` -- ``transition`` is ``''`` for the flow itself -- or ``None``.
The last ``:`` starts the transition; since a flow name may hold ``:``,
``known(name) -> bool``, when given, is asked first whether the whole text is
a flow. ``PK_PLACEHOLDERS`` (what a row link's URL is reversed with in place
of the pk), ``FLOW_PREFIX`` and ``PAGE_PREFIX`` are public too.

``rctx.components`` is the component registry the design is resolved with and
``rctx.resolved`` the ``ResolvedPage`` being rendered (``None`` while
resolving).

**resolve with a context and components.**

.. code:: python

    rctx = EditorContext(document, request, preview=True)
    resolved, errors = engine.resolve(document, context=rctx,
                                      components=my_components)
    rctx.unexposed  # whatever the context collected

``context`` is a ``ResolveContext`` subclass (instantiated by the engine) or an
instance, which gets the upgraded document as its ``design`` and keeps its
errors; ``components`` is a ``{type: component instance}`` dict instead of the
registry. The ``ResolvedPage`` remembers the context class
(``context_class``) and, when it was given one, the instance (``context``).
``engine.render(resolved, request, context=None)`` renders with
``context.copy_for(request)`` -- a copy with the request, its site and user,
and no errors, forms or resolved page; whatever a subclass's ``__init__``
took stays -- or, after a class, with a new one of that class. A subclass
with other per-request state resets it in ``copy_for``; ``render(...,
context=...)`` still takes a context of its own. The positional signature,
``resolve(document, request=None, preview=False, *, allow_templates=False,
allow_js=False)``, is unchanged.

**Facets over other components.** A component whose nodes a ``facets`` panel
may filter sets ``facets_target = True`` and answers ``facets_source(node,
rctx, path)`` with the name of the data source (:doc:`datasources`) its rows
come from -- or ``None`` after ``rctx.error()``. The panel validates its
``columns`` against that source (filterable, not JSON), renders a ``GTFacets``
over ``gtdatasource`` with the group ``gtdesign:<target id>``, and serves no
endpoint of its own: the data source API applies the source's permissions.
The target's widget joins the same ``GTDataSourceState`` group to be
filtered.

.. code:: python

    @register
    class Report(RuntimeComponent):
        type = 'report'
        facets_target = True

        def facets_source(self, node, rctx, path):
            return node['props']['datasource']

**The page's context, theme and breadcrumbs.** ``GT_DESIGNS_PAGE_CONTEXT`` is
a callable ``(request, page) -> dict`` (or its dotted path); what it returns is
added to the context of every design page served at ``designs/<path>``. It can
give the page the theme of whatever mounts it, ``breadcrumbs``
(``[{"label", "href"}]``, which ``gentelella/base.html`` renders in its
``breadcrumbs`` block) or a ``base_template`` of its own; it cannot replace
what the page is (``content``, ``media``, ``page``, ``parent``...: those keys
are ignored and logged). ``gtdesigns/page.html`` extends ``base_template``,
``GT_DESIGNS_BASE_TEMPLATE`` by default (``gentelella/base.html``), and has
three blocks for a template extending it: ``gtdesign_before``,
``gtdesign_content`` (``{{ content }}``) and ``gtdesign_after``.

.. code:: python

    # djodo: the pages of an App get its layout, theme and breadcrumbs
    def design_page_context(request, page):
        return {'base_template': 'djodo/base.html'}

    GT_DESIGNS_PAGE_CONTEXT = 'miapp.designs.design_page_context'

**Conditions with the object.** On a page about one object the page and the
API of each node must decide the same, so a node's conditions get the object
only where its endpoints carry it (``ResolvedPage.takes_parent(node_id)``:
every endpoint has a ``parent_pk`` in its URL, as an inline table and the
facets of one do; a node without endpoints, such as ``html`` or a layout
node, takes it too). For those, the conditions of the node, its ancestors,
columns, actions and row links are evaluated with the object
(``evaluate_condition(cond, request, obj)``) when rendering, and once the URL
is matched when serving (``engine.ObjectConditionResolver``). A node whose
endpoints do not carry it -- a table of every row, a chart, a stat, a classic
CRUD -- is evaluated without the object on the page as in its API, its
ancestors' conditions included: a condition about the object hides it there
(``{"auth": ...}`` that needs an object does not hold). Put such a node
under no condition about the object, or use an inline component.
``ResolvedPage.condition_object(node_id, obj)`` says which object a node
gets; ``ResolvedPage.node_visible(node_id, request, obj=None)`` applies it,
and the nodes a node depends on get their own.
``ResolvedNode.visible(request, obj=None)`` evaluates with the ``obj`` it is
given.

Commands
--------

``gtdesigns_publish <file.json> [--site <domain>] [--path <path>] [--user <username>] [--draft]``
    Validates the design and saves it as the page at ``(site, path)``,
    replacing the one there. ``--path`` defaults to ``meta.url``. Nothing is
    saved when the design has errors: the command fails listing them.
``gtdesigns_export [<path>] [--site <domain>] [--output <file or directory>]``
    Writes one page's document to stdout or a file, or every page of the site
    to a directory (``a/b`` becomes ``a__b.json``). What it writes publishes
    again unchanged, and the editor reads it.

The admin lists the pages and shows the document read only, with a
**Validate** button; adding a page there validates its document first.

Security
--------

A design is data, written by whoever may publish one, so by default it cannot
run code:

- **html is cleaned, not templated.** ``html`` nodes go through nh3 with an
  allow list (``djgentelella.designs.sanitize``): layout and text tags,
  ``class``/``id``/``aria-*``, the ``data-*`` Bootstrap reads to toggle,
  collapse, dismiss and slide (``data-bs-toggle``, ``data-bs-target``... and
  their older names; ``djgentelella.designs.sanitize.DATA_ATTRIBUTES``) and no
  other ``data-*`` -- a ``data-widget`` or ``data-url`` would configure a
  widget of the page --, ``style`` limited to layout and text
  properties, ``http``/``https``/``mailto``/``tel`` URLs. ``<script>``,
  ``<style>``, ``<iframe>``, forms and every ``on*`` handler are removed.
  ``{% ... %}`` and ``{{ ... }}`` stay as text.
- **Template mode** is opt-in twice: ``GT_DESIGNS_ALLOW_TEMPLATES = True`` *and*
  a page whose publisher (``updated_by``) holds ``gtdesigns.publish_template``.
  The template gets ``request`` and ``user``, and its output is cleaned all the
  same.
- **assets.js** works the same way: ``GT_DESIGNS_ALLOW_JS = True`` and a
  publisher with ``gtdesigns.publish_js``.
- **assets.css is cleaned**, not gated, so plain styling works on every page
  (``djgentelella.designs.css.clean_css``). Comments go first (they could
  split a keyword) and CSS escapes of letters and digits are decoded
  (``@\69mport``); then ``@import`` rules are removed and ``expression(``,
  ``-moz-binding``, ``behavior:`` and the ``javascript:``, ``vbscript:`` and
  ``livescript:`` schemes are renamed to ``blocked``, which makes their
  declaration invalid. The steps repeat until a pass changes nothing, so
  removing a rule cannot join the text around it into a new one
  (``@im@import x;port``). The result cannot close its ``<style>`` either. A page
  that may serve ``assets.js`` gets its CSS as written: its publisher can
  already run any script on it.
- The trust follows the publisher: revoking the permission or deactivating
  them turns it off on the pages already served within
  ``GT_DESIGNS_TRUST_TTL`` seconds (60 by default; ``0`` checks it on every
  request). Saving the page again, or publishing it as another user, applies
  at once. A page published from the command line without ``--user`` is never
  trusted.
- Only exposed models, and only their allowed fields, reach a design.
- Publishing from the admin or the command records the publisher; whoever can
  change ``Page`` can publish, so grant ``gtdesigns.change_page`` as you would
  grant editing the site.

Settings
--------

==============================  =========  ================================
Setting                         Default    Meaning
==============================  =========  ================================
``GT_DESIGN_COMPONENTS``        ``[]``     extra components, dotted paths
``GT_DESIGNS_ALLOW_TEMPLATES``  ``False``  html nodes may be templates
``GT_DESIGNS_ALLOW_JS``         ``False``  ``assets.js`` may reach the page
``GT_DESIGNS_LOGIN_REQUIRED``   ``True``   pages need a signed-in user
``GT_DESIGNS_CACHE_SIZE``       ``128``    resolved pages kept per process
``GT_DESIGNS_TRUST_TTL``        ``60``     seconds the publisher's trust is
                                           kept per process
``GT_DESIGNS_BASE_TEMPLATE``    see text   what ``gtdesigns/page.html``
                                           extends
``GT_DESIGNS_PAGE_CONTEXT``     ``None``   ``(request, page) -> dict`` added
                                           to the context of each page
==============================  =========  ================================
