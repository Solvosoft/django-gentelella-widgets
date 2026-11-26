Changelog
===========

0.8.0 (2026-11-26)
--------------------

A large release. The new modules: forms in several steps with drafts
(``djgentelella.wizard``), global search (``djgentelella.search``), PWA and
web push (``djgentelella.pwa``), translations of metadata
(``djgentelella.translations``), a theme roller per Site
(``djgentelella.theme``), user feedback (``djgentelella.feedback``),
optimistic locking (``djgentelella.locking``), the menu as data
(``djgentelella.menu``) and ``djgentelella.authorization``. The design
engine gains the interactive grid, the Kanban board of a flow, the region
components (cards, calendar, map, tree, timeline, metric cards) and the page
pipeline, and the form widgets of the catalog arrive (stars, range, switch,
combobox, QR, Markdown, image crop, LOV popup, geocoded address). Each one is
off or opt-in by default; read **Backwards incompatible** before upgrading.

New features
""""""""""""""""""

**Public API for the tools built on djgentelella.** What they had to copy or
parse is now public, with tests:

* ``djgentelella.menu.item_url(item, context)`` is the link of a
  ``MenuItem``, the one the menu tags draw (``fail_silently=True`` returns
  ``''`` for a broken reverse). A ``url_name`` of ``page:<path>`` links the
  design page published at that path.
* ``djgentelella.flows`` exports ``validate_actions(specs, where='')`` -- the
  allowlist check of a list of actions outside a flow document --,
  ``validate_callables``, ``is_task_form_allowed``, ``validate_task_forms``
  and ``variable_types()``. The validators return ``(path, message)`` errors
  (``DocumentError``, a ``designs.jsonschema.Error``: read ``error.path`` and
  ``error.message``). Each entry of ``registered_flows()`` has
  ``auto``, ``{transition: bool}``. ``djgentelella.flows.variables`` is the
  registry of the types a flow variable can be declared with
  (``register_variable_type``, ``check_variable``).
* ``designs.data_components.parse_flow_link(text)`` reads
  ``flow:<name>[:<transition>]`` without a context, and ``PK_PLACEHOLDERS``,
  ``FLOW_PREFIX`` and ``PAGE_PREFIX`` are public.
  ``ResolveContext.row_link(link, model, path)`` is the hook every row link
  goes through.
* ``CRUDView`` takes ``column_conditions`` and ``action_conditions``, applied
  by its views through ``get_condition_object()``, ``get_hidden_columns()``
  and ``get_denied_actions()``; the classic CRUD of the designs is built on
  them.
* A table's ``update``, ``destroy`` or ``retrieve`` condition that names an
  authorization (``{"auth": ...}``) is evaluated with each row: the API says
  per row which actions it offers and refuses the others with a 403. An
  inline table keeps evaluating them with the object of the page.

See ``docs/source/menus.rst``, ``flows.rst``, ``designs.rst`` and
``crud.rst``.

**Translated document messages and tooling.** The errors of design documents
(``engine.resolve``, the JSON Schema validator, ``format``) and of flow
documents (``validate_callables``, ``validate_task_forms``,
``publish_definition``, ``build_flow``), the errors of a table's ``notify``
prop, the messages of ``validate_condition`` and the
palette labels of the design components are translated, and the ``es``
catalog has them. ``resolve_page`` keeps one resolution per language.
``make messages`` uses the new ``gtmakemessages``, which for ``djangojs``
also reads ``pg_gettext()`` and the inline ``<script>`` blocks of templates
instead of deleting their translations; ``make test`` runs every label, as
the CI, which compiles the ``.mo`` files first (they stay out of git); and
``sphinx-build -W`` passes. A published design page takes two queries once
cached (plus the Site lookup by host when no middleware set
``request.site``), and the trust of its publisher is cached for
``GT_DESIGNS_TRUST_TTL`` seconds (60). ``djgentelella.authorization`` can be
imported before the app registry is ready. The PDF viewer shares a load in
progress of the same URL: it used to start two renders on the same canvas, and
the second could leave it blank. A finished load is not reused, so the same
URL fetches a replaced file again; the viewer is reachable as
``$('.pdfviewer-widget').data('pdfviewer')``. The error about template tags in
a ``notify`` text shows ``{% %}`` instead of ``{%% %%}``. The labels of the flow
variable types (``variable_types()``) and the ``DocumentError`` messages of
``validate_actions`` are in the ``es`` catalog too.

**Menus in three queries.** The menu tags ran several queries per item -- its
permissions, their content types, its children --: about 200 on every page of
the demo. The menu of the Site is now loaded once per request (items,
permissions and content types, three queries whatever its size), shared by
``top_menu``, ``sidebar_menu`` and ``footer_sidebar_menu``, and walked in
memory; the markup is the same. A page of the demo went from 219 queries and
120 ms to 33 and 38 ms. The tree is public for breadcrumbs and site maps:
``djgentelella.menu.menu_tree(request)``, ``visible_items(request,
category)``, ``item_visible(item, request)`` and ``item_permissions(item)``.
``PLACEHOLDER_URL_NAMES`` and ``override_identity`` moved to
``djgentelella.menu`` and are still importable from the template tags. The
children of an item are ordered by ``id``, the order the database returned
before without one.

**Forms that list permissions.** ``str(permission)`` reads its content type,
so a ``Permission`` field drew one query per option: 336 on the menu item
form of a CRUD. ``decore_form_instance`` (the forms of ``CRUDView``),
``gt_formfield_callback`` and the permission management form now load the
content types with the permissions (``djgentelella.forms.querysets``).

**Select2 lookups build their serializer once per view**, not on every request,
which made DRF inspect the model's fields anew each time. The serializer
reads its view from DRF's serializer context (``self.view``, as before).

**The sidebar title of a page.** ``gentelella/app/sidebar.html`` shows the
``sidebar_title`` of the template context when a view passes one, and the
configured ``sidebar_title`` setting otherwise.

**Deploying with moderate resources** (``docs/source/installation.rst``): what
a worker costs, the optional packages DRF imports when they are installed
(about 7 MB per worker that djgentelella does not need), and gunicorn with
threads, ``--preload`` and ``gc.freeze()``. ``make memprofile`` measures it
(``scripts/memprofile/``, not part of the package).

**A request of another Site.** ``djgentelella.sites.site_request(site,
user=None)`` is a synthetic ``GET`` ``HttpRequest`` of a Site (its
``request.site``, the user, its domain as the host), for asking what another
Site answers: ``available_formats(site_request(report.site, user))``, its
conditions, flags and settings. ``resolve_site(site)`` is the lookup it shares
with ``ConditionRequest`` (a Site, an id, or ``None``; an id of no Site raises
``ValueError``). See ``docs/source/sites.rst``.

**A key of their own for the encrypted fields.** ``GTEncryptedText`` and
``GTEncryptedJSONField`` encrypt with ``GT_ENCRYPTION_KEY`` (the base64 of 16,
24 or 32 bytes, ``create_key()``; a list rotates them: the first encrypts,
all decrypt) and still read what the old key, the first 16 bytes of
``SECRET_KEY``, wrote. The stored format is the same. ``manage.py
gtreencrypt [--dry-run] [app_label.Model ...]`` rewrites the old values with
the current key. Without the setting nothing changes. See "The key" in
``docs/source/model_fields.rst``.

**The API messages of designs and data sources are translated**: ``not valid
JSON``, ``must be a list of filter objects``, ``unknown facet column``, ``No
such parent``/``No such object``, the 404/403 of a design endpoint and the 400s
of the data source API (``"columns" is required.``...), with the ``es``
catalog.

**CI runs the consumers.** Two informative jobs (``continue-on-error``) run
the suite of djgentelella-editor (``main``) and of djodo (only when the
repository variable ``DJODO_GIT`` is set) against the djgentelella of the
commit.

**Optimistic locking** (``djgentelella.locking``, off by default): the second
of two users saving the same object gets a clear, translated error -- with
who changed it last and when, if the history knows -- instead of silently
overwriting the first one. ``object_version(obj)`` is the value of the field
``GTLockMeta.version_field`` declares, or a keyed checksum of the editable
fields (many-to-many left out, files by their name).
``OptimisticLockFormMixin`` adds a hidden ``_version`` to a ``ModelForm`` and
checks it in ``clean()`` with the row locked by ``select_for_update()``;
``CRUDView.optimistic_lock = True`` uses it in the update view, inside one
transaction. ``OptimisticLockMixin`` gives a DRF viewset an ``ETag`` on the
detail and takes ``If-Match`` or ``_version`` on ``PUT``/``PATCH``: 409 with
the current version when it changed, 428 when ``optimistic_lock_required``
and none was sent; conditions (403) come first and validation (400) last.
The ``object_management`` design component takes the prop
``optimistic_lock``, and its update modal sends the version it read and, on
a 409, offers to reload the form with the current data without closing. See
``docs/source/locking.rst``.

**Who may see or sign a document of the digital signature**
(``djgentelella.firmador_digital.access``). ``has_document_access(user,
instance, field_name, action)`` is the one rule of the preview endpoint and
of the signing websocket: ``action`` is ``'view'`` (the preview, and
validating a document) or ``'sign'``. By default signing takes the ``change``
permission of the model and the preview ``view`` or ``change``, both also
asked with the object (``user.has_perm(perm, obj)``) for an object
permission backend. ``FIRMADOR_ACCESS_CHECK`` is the dotted path of a
callable with the same signature that replaces it. The widget signs the
reference to the file with ``django.core.signing``
(``sign_document_reference``, its own salt); ``FIRMADOR_REFERENCE_MAX_AGE``
(seconds, unset by default) makes it expire. See
``docs/source/widgets/firmador_digital.rst``.

**``crud_classic`` takes the prop ``optimistic_lock``**, as
``object_management`` does: a boolean, ``false`` by default and validated by
the schema; with ``true`` the generated CRUD is a ``CRUDView`` with
``optimistic_lock = True`` and its update page offers to reload the form
after a conflict. The messages of async_notification's views, the calendar
serializer, the flags view and the inline object management are
translated, with their ``es`` catalog. See ``docs/source/locking.rst``.

**Interactive grid** (``djgentelella.designs.grid``). The design component
``interactive_grid`` edits several rows of a model -- or of a
``ModelDataSource`` over one -- in place, each cell with the widget of its
field, and saves them together: new, changed and deleted rows go in one
``POST save/`` that runs in one transaction with the rows locked, and saves
every row or none. Each row is checked in the order of the optimistic
locking -- 403 (permissions and conditions, per row with an ``auth``), 404,
409 (``version_conflict``, with the current version), 400 (errors by field)
-- and the answer lists what failed in each row. ``columns``, ``editable``
and ``widgets`` are validated against the model; ``edit_conditions`` shows a
column read-only where its condition does not hold. Updates are one
``bulk_update`` and new rows one ``bulk_create`` when the model has no
``save()`` of its own and no signal listens; the number of queries does not
grow with the rows. In the page, changed rows are marked, errors appear in
their cell or row, and a conflict offers to reload that row alone.
``OptimisticLockMixin.version_in_list`` (``False`` by default) adds
``_version`` to every row of a list, with no extra query. The demo publishes
``product_grid`` (``/designs/product-grid``). See ``docs/source/designs.rst``
("Interactive grid") and ``locking.rst``.

**Kanban board of a flow** (``flow_kanban``, a design component in
``djgentelella.designs.flow_kanban``). The objects of a flow as cards, one
column per state, from ``Flow.get_queryset(user)`` and the current Site
(an instance of another Site is left out; ``site_field`` limits the objects
by their own Site). Props: ``flow``, ``states`` and their order (by default
the activities an object can wait in), ``title_field``, ``fields``,
``ordering``, a visual ``limit`` per column and ``page_size`` ("Load more").
Dragging a card, or its "Move to" menu, asks the node's endpoint which
transitions go between both states for that object and user and runs one
with ``Flow.run``: none puts the card back with the reason, several ask which,
one with a form opens it in a modal. The columns the card may go to are
marked when the drag starts. The board takes two queries whatever the number
of cards. An unknown flow, state or field is an error of the document. The
demo publishes the help desk at ``/designs/tickets-board/``. See
``docs/source/designs.rst`` ("Flow kanban") and ``flows.rst``.

**Global search** (``djgentelella.search``). A data source becomes searchable
with ``@searchable(...)`` or ``global_search = GlobalSearch(...)``: fields
and their weights (A-D), the title, subtitle and URL of a hit (a URL name,
``page:<path>`` or a callable), the group label and its icon.
``search(request, query, sources=None, limit=None, offset=0)`` asks each
searchable source the request may read (``has_permission``; one without it is
not queried) through its ``get_queryset``, so rows of other users or Sites
never appear, in **one query per source**: full-text with ``SearchRank`` on
PostgreSQL, plus trigram similarity when ``pg_trgm`` is installed (typos), and
``icontains`` with a weighted score elsewhere. ``search/`` is the results page
(grouped, "see more" per group) and ``gtapis/search/`` the same as JSON. The
box in the top bar (``{% global_search_box %}``, ``gtsearch``) is off by
default: ``GT_SEARCH_NAVBAR = True`` or the Site's ``global_search`` setting
turns it on. ``GT_SEARCH_SOURCES`` chooses the sources of a request. The
optional app ``djgentelella.search.trigram`` creates ``pg_trgm`` with a
migration. ``datasources.query.fulltext_query(text, config)`` is the search box
query both share. See ``docs/source/global_search.rst``.

**A natural key for menu items and the menu as data** (``djgentelella.menu``).
``MenuItem.key`` (optional slug, unique in its Site or among the global
items; migration ``0024``) and ``MenuItem.objects.get_by_natural_key(key,
site_domain=None)``. ``export_tree(site)`` gives the menu of a Site (or the
global one) as a list of trees without pks: the fields, ``permissions`` as
``app_label.codename``, ``children`` and, for a root under a global item,
``global_parent``. ``import_tree(data, site, replace=True)`` checks it all
first (``validate_tree``: types, keys, permissions, conditions, registered
widgets, global parent, depth) and writes nothing when something is wrong;
otherwise, in one transaction, an item whose key names one of the scope is
updated in place, the others are created and, with ``replace``, the items the
data does not name are deleted. See ``docs/source/menus.rst`` ("Exporting and
Importing a Menu").

**Pages and flows as data, published for their Site.**
``designs.publishing.export_page(page)`` / ``import_page(data, site=None,
user=None)`` (``path``, ``title``, ``is_published``, ``document``,
``permissions`` as ``app_label.codename``; checked by ``validate_page_data``,
nothing saved on errors) and ``djgentelella.flows.export_definition`` /
``export_definitions(site)`` / ``import_definition(data, site)`` (``{name,
document}``; the same document is no new version; checked by
``validate_definition_data``). ``publishing.publish`` and ``validate`` resolve
the document for the Site they publish in (``engine.resolve`` and
``make_context`` take ``site=``): a ``flow:`` row link to a flow published only
in that Site was an error and is now valid there. See
``docs/source/designs.rst`` and ``flows.rst``.

**``optimistic_lock_required`` as a design prop.** ``object_management``,
``inline_object_management``, ``crud_classic`` and ``interactive_grid``
accept it (a boolean, ``false`` by default, in their ``props_schema``). It
turns ``optimistic_lock`` on: the table's viewset gets
``optimistic_lock_required = True`` (an update without the version is a 428)
and the classic CRUD the new ``CRUDView.optimistic_lock_required`` (a form
without the version is refused with ``version_required``); a grid with
locking already required it. ``true`` with ``"optimistic_lock": false`` is an
error of the document. See ``docs/source/locking.rst``.

**Exporting and validating a menu say more** (``djgentelella.menu``).
``export_tree(site, warnings=[])`` fills the list with one ``Error`` (the
path of the node in the data and a message) for every item it exports as a
root because its parent is out of the data: an item of another Site, or of a
Site in the global menu. What it returns does not change. ``validate_tree``
takes a ``Site`` not saved yet, so a menu with a ``global_parent`` can be
checked before its Site is created; ``import_tree`` still needs it saved.
See ``docs/source/menus.rst`` ("Exporting and Importing a Menu").

**The grid and the Kanban as public API.** ``designs.grid`` and
``designs.flow_kanban`` list in ``__all__`` what code generated from a design
uses (``GridState``, ``required_fields``, ``NOT_SHOWN``, ``NOT_EDITABLE``,
``board``, ``render_cards``, ``resting_states``...).
``grid_page_context(build, request, url, form_class=None, columns=None)`` and
``kanban_page_context(build, request, url)`` build the context of their
templates -- the cells, the columns and the ``data-gtconfig`` JSON -- from a
build, without a published ``Page`` (``None`` when the request may not see
it); the components render with them. ``FlowKanbanViewSet.get_build()``
serves its ``kanban_build`` class attribute, or else
``request.gtdesign_build``. ``ResolveContext.flow(name, path=None)`` is the
hook every flow a design names goes through (a board, a ``flow:`` row link):
a subclass answers flows that are not published yet. ``page_hash`` is
documented as the factories' cache key only. See ``docs/source/designs.rst``.

**System runs of a flow.** ``Flow.run(obj, name, system=True)`` runs a
transition as the system, like an automatic transition or a ``Deadline``: no
permission is checked, the source state and the condition are, and the log
has no user. The flag is explicit and takes no user (``ValueError``), so
``user=None`` or an anonymous user without it are refused as before.
``Flow.start(obj)`` without a user is documented as a start by the system.
See ``docs/source/flows.rst``.

**Owners and tags of a searchable source; the results page in an
application.** ``searchable(..., owners=[...], tags=[...])`` (fields of
``GlobalSearch``) say who a source belongs to; ``source_owners``,
``source_tags``, ``is_owned_by`` and ``searchable_sources(owner=...,
tags=...)`` are what a ``GT_SEARCH_SOURCES`` hook reads. The results page
extends ``GT_SEARCH_BASE_TEMPLATE`` and adds what ``GT_SEARCH_PAGE_CONTEXT``
returns (a ``base_template``, ``breadcrumbs``, a theme). See
``docs/source/global_search.rst``.

**System events and more actions in the history.** ``add_log(None, obj,
flag, system=True, actor='job')`` records an event without a user: it goes to
the inactive account ``GT_HISTORY_SYSTEM_USERNAME`` (``gt-system``, created
without a usable password when missing) with ``gt_system``/``gt_actor`` in
its ``extra``. ``SECRET_READ`` (6) is a new action, and
``register_action(flag, label)`` adds others: ``add_log``, the history API
and its filter know them. See ``docs/source/history.rst``.

**A chart follows the facets of its page.** The ``facets`` prop of a
``chart`` names a ``facets`` panel; the chart is drawn again with the panel's
filters whenever they change, as its table is. The endpoint takes
``gtfilters`` only on the panel's columns that the table shows the user, and
the panel must filter the chart's rows (a table over its model, or a node
over its data source). See ``docs/source/designs.rst``.

**``make mailhog`` and ``make mailhog-stop``.** Start MailHog in the
background for ``make test-selenium`` (it reuses one already answering on
``:8025``) and stop it.

**Region components: ``cards``, ``calendar`` and ``map``.** Three design
components (``djgentelella.designs.regions``) show the rows of a data source
-- or of an exposed model with an optional ``site_field`` -- with columns by
role (title, subtitle, fields, image, start/end, colour, ``"lat,lng"`` point),
row links with their conditions and ``column_conditions``. They show only the
source's ``get_queryset(request)`` and answer 403 without its permission or
the node's ``perms``. ``cards`` is a ``ListAreaViewset`` read by ``CardList``
(paging, search); ``calendar`` (FullCalendar) reads only the visible range,
at most ``limit`` events, coloured by a column, a value map or the rules of
``color_rules``; ``map`` is a ``BaseMapView`` drawn by ``maplib.js``: popups, optional
clustering, at most ``limit`` points and, as the map moves, only those of the
visible box. A ``facets`` panel filters them (``facets_target``), and
``filtered_by`` makes one panel filter the three. ``ListAreaViewset`` gained
``get_template_context()`` and ``template_response()`` and works without a
``filter_form``; its answer is the same. The demo shows the three over
``demoapp.meetups`` at ``/designs/meetups/``. See ``docs/source/designs.rst``
("Region components").

**Data sources that do not live in the project's database.** A source's
``get_queryset(request, params=None)`` may take the query parameters:
``apply_params``, ``aggregate``, ``pivot``, ``facets`` (each facet without its
own filter), the exports and the API hand it the normalized document through
``query.source_queryset``, and a source without ``params`` is called as
before (``takes_params``). ``DataSourceUnavailable`` (a DRF ``APIException``)
is what a source raises when it cannot read now: every endpoint answers it
with 503 (or the 502/504 it carries, and ``Retry-After``), apart from the 400
of bad parameters. ``validate_params`` never evaluates the queryset, and
``build=False`` does not even build it. The CSV export reads its first chunk
before returning the response, so a read error is an HTTP status and not a
file cut after its header. ``DataSource.project_model`` names the model of
the project behind a source (``project_model_of(source)``), and is what
djgentelella reads instead of ``getattr(source, 'model', None)``. See
``docs/source/datasources.rst``.

**Read-only tables over any data source.** ``object_management`` takes a
``datasource`` instead of ``model`` and ``form`` (list mode): a DataTable of
its rows, with search, ordering, ``column_conditions``, a ``facets`` panel and
row links when the source is over a model of the project, and no modals.
``interactive_grid`` over a data source that is not a ``ModelDataSource`` is
read only (no ``editable``, no ``actions``) instead of an error. Both read
through ``djgentelella.designs.source_tables`` (``SourceTableViewSet``,
``SourceGridViewSet``). See ``docs/source/designs.rst``.

**``default_form(model, fields=None)``** in ``djgentelella.designs.forms``:
the ``forms`` entry a model gets by default (the fields of
``is_form_field``), the one djgentelella-editor imports.

**The calendar speaks the page's language.** ``calendar`` loads FullCalendar's
locales (``locales-all.global.min.js``, now downloaded by ``loaddevstatic``)
on a page that is not in English. The cost of the map's bounding box is
documented.

**``scripts/patch_pylp.py`` works on Python 3.13.5.** It wraps
``runner.future`` in ``asyncio.ensure_future`` -- which takes the ``Future``
of a task and the coroutine of a task with dependencies -- in ``cli/run.py``
and in ``lib/runner.py``, and repairs an install patched with
``create_task``, which broke the tasks without dependencies.

**Regions, read-only tables and facets panels without a published page.**
``RegionMixin`` (``CardsViewSet``, ``CalendarViewSet``, ``MapViewSet``) and
``SourceRowsMixin`` (``SourceTableViewSet``, ``SourceGridViewSet``) take
``region_build`` and ``get_build()``, as ``FlowKanbanViewSet.kanban_build``:
the class attribute wins, else ``request.gtdesign_build``, else 404.
``regions.region_page_context(build, request, url)`` and
``data_components.facets_page_context(build, request, datasource_url=None)``
return the context of the component's template (``template`` included) or
``None`` without permission, like ``grid_page_context``; with them generated
code draws a region, ``filtered_by`` and the ``facets`` of a chart without
building a ``ResolveContext``. ``check_access`` (the contract of the 403),
``read_rows``, ``request_params`` and ``RegionMixin`` are in ``__all__``. See
``docs/source/designs.rst``.

**Columns for a Site without a request.** ``DataSource.columns_for_site(site)``
(by default ``columns(site_request(site))``) and
``source_column_map(source, request=None, *, site=None)``: a page of a Site
validated or published offline reads the columns of its data sources for
that Site (``ResolveContext.source_columns``), so a source whose columns
depend on the Site validates. A ``ModelDataSource`` column over a
``GTPointField`` carries ``extra={'point': True}``.

**``table_page_context(build, request, url)``** draws ``object_management``
in list mode without a published page (``row_link_config`` is public), and
``grid.grid_can_edit(source)`` says whether a grid over a data source edits.

**``load_default_settings()``** in ``djgentelella.utils`` creates the global
settings the migrations load (``DEFAULT_SETTINGS``), for the tests that flush
the database (``TransactionTestCase``, live server). **``djgentelella.testing``**
has ``mouse_click(driver, element)``, a Selenium click after scrolling the
element to the centre without Bootstrap's smooth scrolling, also a method of
the demo's ``SeleniumTestCase``. See ``docs/source/demo.rst``.

**Form widgets of the catalog.** ``StarRatingInput`` (with ``RatingField``),
``SwitchInput`` (Bootstrap's ``form-switch``), ``RangeInput`` (with its value
beside it) and ``RangePairField``/``RangePairInput`` (a minimum and a maximum),
``ComboboxInput`` (select2 with ``tags``: a value of a list or a new one, as
text) and ``QRCodeInput`` (the value drawn as a QR code, ``scan=True`` reads
one with the camera; ``{% qrcode value %}`` in ``gtqrcode``) in
``djgentelella.widgets.extras``; ``LOVPopupSelect`` (a LOV searched in a modal,
page by page); ``MarkdownInput`` with a server preview
(``gtapis/markdown/preview/``) and the ``markdown`` filter (``gtmarkdown``),
both through ``djgentelella.markdown.render_markdown``, which cleans the HTML
with nh3 (the ``[markdown]`` extra); ``ImageCropInput`` (Cropper.js in the
browser) with ``ImageCropField``, which checks image, format and size on the
server (``GT_IMAGE_MAX_SIZE``); and ``GeocodedAddressInput``, an address that
fills a ``GTPointField`` through ``gtapis/geocode/`` and a geocoder of
``GT_GEOCODER`` (``djgentelella.geocoding``, off by default). ``widgetmap``
offers them at the end of the lists of their kinds, so no default changes.
Cropper.js 1.6.2, qrcode-generator 1.4.4 and jsQR 1.4.0 come with
``loaddevstatic`` and are loaded by the widget that needs them, never bundled.
Demo at ``/formwidgets/``; see ``docs/source/widgets/formwidgets.rst``.

**Tree, timeline and metric cards.** Three more region components
(``djgentelella.designs.tree_timeline_metrics``, registered after ``map``)
over a data source or an exposed model, with the Site, permissions (403),
conditions, facets and ``filtered_by`` of ``cards``/``calendar``/``map``:
``tree`` (each row under its ``parent_field``, one level per request or all
at once up to a limit; a missing parent or a cycle goes to the root, marked,
and never hangs the page), ``timeline`` (newest first, paged backwards with a
keyset cursor, a colour per value or by rules) and ``metrics`` (KPI cards:
``count``, ``count_distinct``, ``sum``, ``avg``, ``min`` or ``max`` over a
column, with filters, a number/currency/percent format and the change against
the previous day, week, month, quarter or year, coloured by
``higher_is_better``; every card in one query). No new library. The demo has
them at ``/designs/insights/`` (new model ``demoapp.Department``). See
"Tree, timeline and metrics" in ``docs/source/designs.rst``.

**Page pipeline.** A design page declares what happens before it is drawn
and when one of its forms is sent (``djgentelella.designs.pipeline``): steps
registered in Python by name (``register_process(name, fn, kind=...)`` or
``@process``) of three kinds -- ``validation`` (errors per field or general;
nothing is saved), ``computation`` (values set before the save: fields of the
form, or others the step declares in ``writes``, never the version of
optimistic locking) and ``process`` (in the transaction of the save; an error
rolls all of it back, is shown and is logged without the data) -- and
``branches`` that say where to go (``page:``, ``flow:``, a URL name or a
local path, by condition). The props are ``pipeline.on_submit`` of
``object_management``, ``inline_object_management`` and ``crud_classic``,
and ``pipeline.before_render`` of the page, which can add context, refuse
the page (403) or redirect. Unregistered steps, params that do not fit the
step's schema, bad ``writes`` and a ``before_render`` that loops back to its
page are errors of the document when it is published. ``run_pipeline()``
is public for other senders (a wizard, a view); ``ResolveContext.
pipeline_step()`` is the hook for the steps a design names. The demo order
page (``/designs/shop-orders/``, new models ``demoapp.ShopItem`` and
``ShopOrder``) checks the stock, computes the total, takes the stock and goes
to another page. See ``docs/source/pipeline.rst``.

**Translations of metadata.** What an administrator writes as data
is translated without ``.po`` files (``djgentelella.translations``): a
design page keeps its texts by language in ``document["translations"]``
(keys ``meta.title`` and ``<node id>:<prop path>``, only the props a
component declares in ``RuntimeComponent.translatable_props``), a menu item
in ``MenuItem.translations`` and a LOV value in the ``LOVTranslation`` table
(migration ``0028_translations``). Each is shown in the active language,
else its base language, else the default language, else as written
(``translations.pick``); always escaped. ``engine.resolve(...,
translate=True)`` resolves a page in the active language and the cache of
resolved pages keeps one per language. ``object_management``,
``inline_object_management`` and ``interactive_grid`` take ``column_labels``
(column headers, translatable). The translations travel with
``export_page``/``import_page`` and ``export_tree``/``import_tree``, and
unknown languages (``GT_TRANSLATION_LANGUAGES``, else ``LANGUAGES``) are
errors. ``/gt-translations/`` has a screen per page, the menu and each LOV,
what is missing per language, and exports and imports a JSON file by natural
keys (also ``gttranslations_export``/``gttranslations_import``).
``register_lov(..., all_values=)`` lists the values of a LOV with parents.
The demo switches between Spanish and English from the top bar
(``/designs/translated/``). See ``docs/source/translations.rst``.

**Data sources, OpenAPI and push: smaller additions.** ``restricted(source, columns)`` /
``DataSource.with_columns()``: a data source with only some columns;
``DataSourceView.get_source`` documented as the hook,
``DataSourceExportView.use_export_handler``,
``GT_DATASOURCE_QUERY_TIMEOUT`` (a 504 past it; ``query_timeout()``) and
``GT_DATASOURCE_EXPORT_REFUSE_OVER_LIMIT`` (a 400 instead of a cut file).
``djgentelella.designs.openapi`` describes what each design viewset reads
(``openapi_parameters``), and the ``SerializerMethodField`` of the designs and
of select2 have type hints. The wizard documents that the errors of its final
pipeline come back on its last step. PWA: ``pwa_scope`` per Site,
``GT_PUSH_QUEUE`` (Celery), ``pushsubscriptionchange`` handled through
``/pwa/push/resubscribe/`` and ``GT_PUSH_UNSUBSCRIBE_ON_LOGOUT``. A row
link may name the design page being published itself (master-detail
on its first publication); ``meta.parent.choose`` serves a page about one
object without its pk as the list of objects to choose from;
``Flow.unreachable_states()`` and ``Flow.dead_ends()``; ``factories.site_rows``
in ``__all__``. See ``datasources.rst``, ``designs.rst``, ``flows.rst``,
``wizard.rst`` and ``pwa.rst``.

**Feedback reviewers, public views, login blocks and the user menu.**
``GT_FEEDBACK_REVIEWER(request, user) -> bool`` (and ``GT_FEEDBACK_ANSWERER``)
decides who reviews and answers the feedback of the request's Site, with
``feedback.conf.is_feedback_reviewer``/``can_answer_feedback``; the views a
browser reads before signing in (theme, PWA, JavaScript catalog, flags, login,
logout, password reset) carry ``gt_public = True`` and
``djgentelella.public.is_public_view(match)``/``public_view`` let an access
middleware through without naming them; the manifest's ``scope`` and
``start_url`` follow the request's script prefix when ``GT_PWA_SCOPE`` is not
set; ``gentelella/registration/login.html`` has the blocks ``login_form``,
``login_messages`` and ``login_providers``; the user menu of the top bar is the
menu widget ``gt-user-menu`` with entries a project registers
(``menu_widgets.user.register_user_menu_entry``); ``SiteTheme`` accepts
``#rgb`` and stores ``#rrggbb`` in lower case (``theme.values.normalize_color``).
``widgetmap.register_widget(key, path, options_schema, kinds=,
checks=)`` offers a widget of the project in ``widget_choices``,
``build_widget``, the forms of a design and the editor; ``register_process(...,
tags=)`` with ``registered_processes(tag=)`` and ``catalogue(tag=)`` (each entry
has ``tags``); ``DataSource.row_key(row)`` and ``key_columns`` give a stable key
to the rows of a source without a model; ``Textarea(actions=[WidgetAction(...)])``
draws buttons under the field. The engine reads
``meta.master_detail`` -- the master of the page marked in its table, a click
on a row opens that master's page -- and ``designs/data_components.js``
exposes ``gtdesign_select_row`` and ``gtdesign_master_detail``. See
``feedback.rst``, ``authorization.rst``, ``pwa.rst``, ``templates.rst``,
``menus.rst``, ``theme.rst``, ``widgets/formwidgets.rst``,
``widgets/core_inputs.rst``, ``pipeline.rst``, ``datasources.rst`` and
``designs.rst``.

**Smaller additions to flows and designs.** ``CardsViewSet`` declares ``page_size`` in its
``openapi_parameters``; ``Flow.is_endless()`` and ``dead_ends()`` is empty for a
flow without final activities (a cycle never finishes by design);
``factories.site_rows_by_field(queryset, site_field, request)``; a row link
``page:<path>`` names the page being published at that path even when it is not
its ``meta.url`` (``data_components.publishing_path``, ``links_to_itself(...,
path=)``). See ``flows.rst`` and ``designs.rst``.

**Widget options in the designs.** ``widgetmap.WIDGET_OPTIONS``
declares, as a JSON schema per option, the options a widget takes:
``StarRatingInput`` (``stars``, ``readonly``), ``RangeInput`` (``min_value``,
``max_value``, ``step``, ``show_value``, ``suffix``), ``ComboboxInput``
(``choices``), ``QRCodeInput`` (``scan``, ``readonly``, ``size``),
``ImageCropInput`` (``aspect_ratio``, ``max_width``, ``max_height``,
``output_type``, ``quality``), ``GeocodedAddressInput`` (``point_field``,
``replace_text``), ``MarkdownInput`` (``rows``) and ``SwitchInput``
(``label``). ``widget_options(key)`` is the object schema of one widget,
``validate_widget_options(key, options)`` its errors and
``build_widget(key, options)`` the instance. A design form (and an
``interactive_grid``) takes ``widget_options`` by field, validated with the
design: an option the widget does not declare, a value out of its schema, a
fractional range on an integer field, a ``point_field`` that is not a point
field of the form or options for a widget without them are errors; nothing
reaches the constructor as a free keyword argument. The JSON schema validator
also reads ``maxLength``, ``maxItems`` and ``exclusiveMinimum``. See
``docs/source/designs.rst`` and ``widgets/formwidgets.rst``.

**Facets over a read-only grid and aggregates ordered by value.** A
``facets`` panel can target an ``interactive_grid`` over a data source that is
not over a model of the project: ``SourceGridViewSet`` reads ``gtfilters``,
as the list, and the grid follows the panel (``datasource_url``/``group`` in
its configuration, ``source_tables.facets_config``; ``grid_page_context``
takes ``datasource_url=``). The parameter document takes ``"order_by_value":
true``: ``aggregate()`` returns the groups from the largest first aggregate
down (a saved report can ask for it); ``order_by_value=`` of the call still
wins. ``max``/``min`` over ``date`` and ``datetime`` columns are covered by
tests through ``aggregate``, the API and ``validate_params``. See
``docs/source/datasources.rst``.

**Wizard: forms in several steps with drafts.** ``djgentelella.wizard``:
``GTWizardView`` and ``Step`` -- one form per step, a Bootstrap 5 progress
bar, "Previous", "Next", "Save draft", "Finish" and "Discard", all plain
posts (no javascript to move). Steps are skipped by a ``condition`` (a
callable over the earlier steps' ``cleaned_data_for()`` or a condition of
``djgentelella.authorization``); "Finish" validates every step again and runs
``done()`` in one transaction, with the hooks ``on_step`` and ``on_finish``;
``optimistic_lock`` when editing. Drafts in the session (default) or in the
new model ``WizardDraft`` (migration ``djgentelella.0025_wizarddraft``: user,
Site, key, data, uploads), only ever found for their own user and Site (404
otherwise), expiring after ``GT_WIZARD_DRAFT_EXPIRATION`` (30 days) and
deleted by ``manage.py delete_expired_wizard_drafts``. Files go through the
chunked upload: only the user's own uploads are taken, kept alive while the
wizard runs (new ``FileChunkedUpload.consume_upload``) and by a live draft
(``delete_expired_uploads`` leaves them), and deleted when it finishes. The
design component ``wizard`` (``djgentelella.designs.wizard``) does the same
over one exposed model: steps with fields, ``condition`` and ``when``,
``perms``, ``site_field``, ``mode: "edit"`` on a page about the object with
``optimistic_lock``; new ``x-widget`` hints ``wizard-steps`` and
``step-when``. Demo: ``/wizard/employee/`` and ``/designs/employees/new/``.
See ``docs/source/wizard.rst``.

**The page pipeline inside the wizard.** A ``Step`` takes
``pipeline=`` and ``GTWizardView`` a ``pipeline`` attribute: an ``on_submit``
stage of ``djgentelella.designs.pipeline`` (``{"steps", "branches"}``) or a
``PipelineBuild``. The pipeline of a step runs its validations and
computations whenever the step validates -- an error keeps the user in the
step, a computed value goes to the form and to ``state['computed']``, so a
draft keeps it --; a process or a branch there is refused. The pipeline of
the wizard runs when it finishes: validations and computations with the data
of every step, then ``done()``, ``on_finish()`` and the processes in one
transaction (a failing process rolls everything back and the wizard stays at
its last step with the error), and the branch that holds is where it goes
instead of ``success_url``. ``done()`` saves the fields computed outside the
forms (``writes``; ``extra_values()``). The ``wizard`` component takes
``pipeline`` on the node and on each step, checked when the document is
published. New: ``pipeline.build_pipeline(stage, model=, form_fields=,
intermediate=)`` builds a pipeline in code; ``resolve_pipeline`` takes
``intermediate=`` and ``where=``. Computations must be idempotent: a step
validates more than once. See ``docs/source/wizard.rst``.

**``site_field`` in the forms of a model.** ``object_management`` and
``crud_classic`` take ``site_field`` (a foreign key to ``sites.Site``): the
rows are those of the request's Site and the global ones, another Site's row
is a 404 (detail, update, delete), and a new row gets the request's Site. The
form cannot ask for it, and the default form of ``crud_classic`` leaves it
out; a ``facets`` panel over the table counts the same rows. See
``docs/source/designs.rst``.

**A geocoder per request.** ``GT_GEOCODER`` can name a function -- or
be one -- that takes the request and returns its ``Geocoder`` (or ``None``):
one per Site, with the key read from the Site's credentials, without global
state. ``get_geocoder(request=None)`` and ``geocoder_configured()``;
``gt-geocode`` passes the request. A class keeps working as before. See
``docs/source/widgets/formwidgets.rst``.

**Metrics and facets for generated code.** A metric card takes its own
``period`` (one of the periods, or ``"all"``: every row, no comparison --
"total" next to "new this month"); each card carries ``period``,
``period_label`` and ``compare_label``. ``MetricsComponent.page_context()``
adds ``cards``, ``cards_html`` and ``unavailable``, so
``region_page_context()`` draws a metrics node without a page, and
``render_cards`` is public. A chart bound to a ``facets`` panel copies the
``column_conditions`` of the panel's target into ``ChartBuild.
facet_conditions`` when the page is resolved, and ``chart_facet_filters`` no
longer needs ``request.gtdesign_resolved``. ``facets_viewset_for(build,
target=None)`` (or ``FacetsBuild.target_build``) and
``facets_page_context(build, request, url=, target=)`` serve a panel over a
table of a model without a published page. See ``docs/source/designs.rst``.

**Markdown columns.** A field of the form of an ``object_management``
written with ``MarkdownInput`` is a Markdown column: its rows and its detail
carry ``<name>_html`` (cleaned by ``render_markdown``), the table shows it
and the detail modal prints it as HTML; the text itself never is. For
``ObjectCRUD`` in code: ``djgentelella.serializers.GTMarkdownHTMLField`` and
the ``markdownprint`` renderer of ``datatables.js``.

**The pipeline for generated code.**
``PipelineFormMixin`` (a ``CreateView``/``UpdateView``),
``PipelineViewSetMixin`` (``perform_create``/``perform_update``, the branch
as ``gtdesign_redirect``) and ``PipelinePageMixin`` (``before_render`` before
a ``GET``) take a ``pipeline`` stage; ``run_form_pipeline``,
``run_serializer_pipeline`` and ``run_before_render`` are the functions under
them. ``data_components.js`` exports ``window.gtdesign_pipeline_events`` (the
modal events that follow ``gtdesign_redirect``). A step of the document may
say its ``kind`` (checked against the step, and given to a
``pipeline_step`` hook that takes ``kind=``); ``step_build(name, kind,
function, ...)`` builds a step without registering it. New hook
``ResolveContext.branch_target(target, path, *, event, model)`` (default
``pipeline.resolve_branch_target``) for branch targets a tool generates.
``catalogue()`` and ``Process`` carry the ``app`` that defines each step.
The steps of a ``wizard`` take ``widget_options``.

**The project's ResolveContext everywhere a page is published.** The
new setting ``GT_DESIGNS_RESOLVE_CONTEXT`` (a ``ResolveContext`` subclass or
its dotted path) is the context every design is resolved with when the caller
gives none: ``gtdesigns_publish``, the admin, ``publishing.publish``,
``validate`` and ``import_page`` (and the APIs built on them),
``engine.resolve_page`` when a page is served (the class is part of its cache
key), ``pipeline.build_pipeline`` and ``region_page_context``. A rule such as
djodo's "a page of an App names only that App's pipeline steps" then holds on
every path, not only on the project's own. ``publish``, ``validate``,
``import_page`` and ``build_pipeline`` take ``context=``, which wins;
``components.default_context_class()`` returns the configured class. Adding a
page in the admin validates it for the Site of the form and with the trust of
the user adding it, as ``publish`` does; **Validate** resolves a page for its
own Site.

**Facets over a region or a grid of a model.** A ``facets`` panel may
target a ``cards``, ``calendar``, ``map``, ``tree``, ``timeline``,
``metrics`` or ``interactive_grid`` node over an exposed ``model`` (before,
only over a ``datasource``): it counts through its own endpoint over the rows
of that node -- its ``site_field`` and, for a region, its ``perms`` included
--, and the node follows it by its group (``gtdesign:<target>``; the browser
reads the panel's ``data-url``). ``filtered_by`` from another region over the
same model and ``site_field`` works too. A component opts in with
``RuntimeComponent.facets_model = True``; ``regions.facets_state(build)`` is
the state a region's configuration names. A grid whose rows are pending
applies a facet that changed once they are saved or undone.

**``site_field`` in the interactive grid, defaults of step params, geocoder
options.** ``interactive_grid`` over a model takes
``site_field``, as ``object_management``: the rows of the request's Site and
the global ones, another Site's row is a 404 in a batch, a new row gets the
request's Site. The ``default`` of a property of a step's params schema fills
what the document leaves out (``pipeline.param_defaults``,
``with_param_defaults``; ``step_build`` too). ``NominatimGeocoder`` takes
``extra_params`` and ``extra_headers`` (the key of a compatible service).

**Pipeline context and facets for project code.** ``PipelinePageMixin.get_pipeline_parent()`` and
``get_pipeline_page()`` give the steps their ``ctx.parent`` and ``ctx.page``.
``designs.factories.GTFiltersMixin`` (``gtfilters_fields``) lets a viewset of
the project follow a facets panel, and ``window.gtdesign_follow_facets(id,
crud)`` / ``window.gtdesign_facet_filters(id)`` link an ``ObjectCRUD`` of
generated code to it.

**The ``app`` of a document.** ``app`` and ``slug`` stay lower-case
Python identifiers (``format.APP_PATTERN``): ``app`` is a Django app label for
code generation, flows and pipeline steps (``<app>.<step>``).
``format.app_name(slug)`` turns a slug with ``-`` (a djodo App) into one.

**Theme roller per Site.** ``SiteTheme`` (migration ``0026``) holds the
Bootstrap colours, the sidebar's, the border radius, a font of a fixed list and
a logo of a Site, or the global theme. Only typed, validated values (``#rrggbb``,
0-24 px, PNG/JPEG/GIF/WebP checked with Pillow), never CSS: the stylesheet is
written from them (``theme.css.render_css``) and served at
``/gt-theme/<pk>.css?v=<version>``, cached for a year and fetched again when the
theme is saved. ``{% gt_theme_css %}`` links it from ``base.html``; the sidebar
shows the logo. The page ``gt_theme_roller`` edits it with a live preview. See
``docs/source/theme.rst``.

**The diagram of a flow instance.** ``Flow.instance_diagram(obj, user)``
highlights the current activity, the transitions taken (from the log) and the
transitions the user may run now (``data-transition``), and says it in a
``<title>``/``<desc>`` for screen readers; ``Flow.runtime()`` adds ``taken`` and
``path``. ``flow_detail`` uses it, and ``{% flow_diagram object %}`` finds the
flow of the object (``flow=`` names it).

**User feedback.** With ``GT_FEEDBACK = True``, a button of ``base.html``
(``{% gt_feedback_button %}``) sends an error, an idea or a question, with the
page and the browser if the user agrees, never form data. ``Feedback`` (same
migration) is reviewed at ``gt_feedback_inbox`` (``view_feedback``) and answered
at ``gt_feedback_detail`` (``change_feedback``), which notifies its author. A
Site turns it off with the setting ``feedback_enabled``. See
``docs/source/feedback.rst``.

**Choices of a relation by Site.** ``expose(model,
site_field='site')`` makes every relation to that model in the forms of
``object_management``, ``crud_classic``, ``wizard`` and ``interactive_grid``,
their serializers (``factories.SitePrimaryKeyRelatedField``) and the model's
select2 lookups (``BaseSelect2View.site_field``) offer the rows of the
request's Site and the global ones; another Site's row is refused.
``exposure.site_choices``, ``limit_form_choices``, ``site_field_of``;
``FormBuild.get_form(request=)``.

**PWA and web push.** ``djgentelella.pwa``: a web app manifest per
Site at ``/pwa/manifest.webmanifest`` (name, short name, colours, icons and
start URL from the ``pwa_*`` keys of ``GentelellaSettings``, Site's over
global), its tags in the new ``pwa_head`` block of ``base.html`` behind
``GT_PWA_MANIFEST``; a service worker at ``/pwa/sw.js`` registered behind
``GT_PWA_SERVICE_WORKER``, with a versioned cache of the static files only
(``GT_PWA_CACHE_VERSION``; pages and APIs are not cached) and an offline
page, which unregisters itself when the setting is turned off; and web push
(VAPID) of the notifications: ``PushSubscription`` per user and device (with
its Site) and ``PushPreference`` (migration ``0026_push_subscriptions``),
every new ``Notification`` sent to its user's subscriptions after the commit
through a pluggable backend (``GT_PUSH_BACKEND``; ``WebPushBackend`` with
``pywebpush``, the new ``[push]`` extra, or ``LocmemPushBackend``), expired
subscriptions (404/410) deleted, ``send_push()`` for anything else, the user's
page at ``/pwa/push/`` (subscribe, unsubscribe, test, turn off) and
``manage.py gt_vapid_keys``. Without the extra or the keys push is off and
everything else works. See ``docs/source/pwa.rst``.


Backwards incompatible
""""""""""""""""""""""""

**async_notification: a pending upload belongs to its uploader.**
``/preview-file/<pk>/`` and ``/preview-video/<pk>/`` served any upload not
linked yet (``object_id=0``) and any inline image to every user of the module,
by sequential pk. A pending upload is now served only to the user who
uploaded it (one without an uploader needs ``change`` on its model), and an
inline image of a notification needs ``view`` or ``change`` on it; the inline
images of email and newsletter templates stay visible to every user of the
module. ``preview_file_view`` streams the file (``FileResponse``) instead of
reading it whole into memory.

**The translation screens work on the request's Site.** ``gt-translations/``
listed and saved the menu items of every Site and opened any page by pk. They
now take the request's Site and the global objects (another Site's page is a
404), and the import refuses a LOV the user may not open. The
``gttranslations_*`` commands still move every Site.
``export_translations``, ``import_translations`` and
``validate_translations_data`` take ``request=`` and ``site=``.

**Select2 lookups of an exposed model are filtered by Site.** A
``BaseSelect2View`` whose model is ``expose()``\ d to the designs with a
``site_field`` now answers only the rows of the request's Site and the global
ones, without any change in the view: ``site_field_of(model)`` is its default
``site_field``. A lookup that must keep listing every Site's rows sets
``site_field = ''``.

**Conditions of a table's row actions about the object get the row.** In a
table that is not inline, an ``update``, ``destroy`` or ``retrieve`` condition
that names an authorization (``{"auth": ...}``) used to be called with
``obj=None`` and now gets each row: an authorization that allowed ``None``
may now refuse some rows (403 and no button), and one that refused ``None``
may now allow some. An inline table is unchanged: its conditions still get
the object of the page. ``validate_callables`` and ``validate_task_forms``
return ``DocumentError`` tuples instead of ``'path: message'`` strings: read
``error.path`` and ``error.message``. ``str(error)`` is still that text, but
an error is not equal to it (``DocumentError('a', 'b') == 'a: b'`` is
``False``), ``in`` looks into the tuple and the ``str`` methods
(``partition``, ``startswith``...) are gone; the bridge that answered them
while the editor and djodo moved to ``path``/``message`` was removed before
the release.

**Translated validation messages and cached trust.** The errors of design and
flow documents and of ``validate_condition`` follow the active language:
code that compares them with English text runs under
``translation.override('en')``. Revoking ``gtdesigns.publish_template`` or
``publish_js`` from a page's publisher, or deactivating them, reaches the
pages already served within ``GT_DESIGNS_TRUST_TTL`` seconds (``0`` restores
the check on every request). ``ConditionRequiredMixin`` is defined in
``djgentelella.views.conditions``; importing it from
``djgentelella.authorization`` still works.

**Upload tokens outside the form widgets belong to who presents them.**
``ChunkedFileField`` and ``DigitalSignatureField`` (DRF), the digital
signature websocket and the document preview
(``DigitalSignatureRenderFileAPIView``) took the ``ChunkedUpload`` of a token
whoever uploaded it, and in whatever state. They now take only a finished
upload of the user of the request (an anonymous visitor, only the uploads
without a user): another user's token, or one of an unfinished upload, gives
no file, and the preview answers 404 (it answered 200 with the text
``None``). A serializer used without a request takes the upload whoever
uploaded it, but still only a finished one.
``djgentelella.chunked_upload.utils.find_upload(token, user)`` is the lookup.
Finished is ``status=COMPLETE`` or a ``completed_on``: an upload created by
hand with ``completed_on`` but no ``status`` (whose default is ``UPLOADING``)
still counts, as it did before.
The form widgets do not see the request and keep taking the token whoever
uploaded it, on purpose: ``FileChunkedUpload`` and ``FileInput`` as before,
``DigitalSignatureInput`` now only a finished upload; ``UserFileChunkedUpload``
takes the user's own.

**The digital signature only reads the document the server named, for a user
allowed to use it (security fix).** The preview endpoint
(``DigitalSignatureRenderFileAPIView``), the signing websocket
(``InstanceSerializer``), ``DigitalSignatureInput`` and
``DigitalSignatureField`` took ``{contenttype, pk, field_name}`` from the
browser, and ``check_user`` returned ``True``: any signed-in user could see or
sign the file of any object of any model. Now:

* the widget renders a signed reference instead of that base64 JSON, and
  only a signed reference names a file: an unsigned or altered one gives no
  file. A value the browser builds itself can only carry an upload token.
  A page rendered before the upgrade has to be reloaded.
* the preview requires the reference to name the content type and pk of its
  URL, and ``check_user`` asks ``has_document_access``: ``view`` or
  ``change`` on the model. The websocket asks the same with ``change``.
  Users who signed with no permission on the model are refused until they
  get one or the project sets ``FIRMADOR_ACCESS_CHECK``.
* every refusal of the preview is the same 404 ``File not found`` (a
  ``check_user`` that returns ``False`` answered 403), and every refusal of
  the websocket the same ``The document is not available.``, so neither tells
  whether the object exists.
* ``DigitalSignatureField`` only takes a reference to its own field of the
  serializer's instance.
* ``ValueDSParser.get_json_file`` and ``InstanceSerializer.get_json_file``
  return ``None`` for an unsigned reference; code that built one by hand
  calls ``sign_document_reference(instance, field_name)``.

To keep the old rule of access on purpose -- any signed-in user may see and
sign the documents the widget shows him -- point ``FIRMADOR_ACCESS_CHECK``
to a function of your own that returns ``user.is_authenticated``. The
signature of the references cannot be turned off.

**A form only changes the file of its own object, and async_notification
checks the object (security fix).**

* ``DigitalSignatureInput`` turned any signed reference into that object's
  file, so the reference of object X posted in the form of object Y copied
  X's file into Y. A reference posted back now means "unchanged": the
  widget returns ``None`` and the field keeps its initial value (in a
  ``ModelForm``, the file of its instance). Only the token of a signed copy
  changes the file. A plain ``forms.Form`` that read the file from the
  reference has to pass it as ``initial``.
* ``reassociate-files/`` linked the uploads of any ``upload_session`` to any
  object of any model. It now takes only the models of async_notification
  (400 for another ``content_type``), an object that exists and that the
  user may change -- or created, with the ``add`` permission -- (404
  otherwise), and only the files the same user uploaded in the same login
  session.
* ``preview-file/<pk>/`` served any attachment to any user with a permission
  of the module. A file attached to an object (the attachment of a
  notification) now needs ``view`` or ``change`` on that object (404
  otherwise); inline images and uploads not yet linked are served as before.
* ``<pk>@<app_label>.<model>.internal`` resolved a row of any model with an
  ``email``, and the recipients preview showed it. It now resolves only the
  user model, the models with ``gt_get_mail_address()`` and those listed in
  the new ``ASYNC_NOTIFICATION_INTERNAL_MODELS``; any other gives no address.
  List there the models whose ``email`` you addressed this way.

**async_notification: uploads belong to their uploader, videos go through a
view, and the download name is escaped (security fix).**

* Saving a body that named the pk of somebody else's pending image linked
  that image to the new object. ``AttachedFile`` records ``uploaded_by``
  (migration ``0009``), and ``sending.link_body_attachments(instance,
  user=None)`` moves only the pending uploads of ``user`` and those without
  an uploader (files created by code or before the migration); without a
  user, only the latter. The API serializers pass the user of the request, and
  ``reassociate-files/`` also checks the uploader. It links the videos of the
  body too.
* ``upload-video/`` answered the file's ``MEDIA_URL``, served wherever the
  project serves media and outside any permission. It now answers the new
  ``preview-video/<pk>/``, which has the permissions of ``preview-file/`` and
  serves the video with its content type (bytes when its name is not a
  video). Bodies saved before keep their media URLs.
* ``preview-file/<pk>/`` pasted the stored name between quotes in
  ``Content-Disposition``. It sends the base name through Django's
  ``content_disposition_header``.

**Menu widgets are registered** (``djgentelella.menu``). A ``MenuItem`` with
``is_widget`` made the menu tags import and call whatever dotted path its
``url_name`` held. The menu now builds only the widgets the project declares:
djgentelella's own (``PalleteWidget``, ``NotificationMenu``), a class
decorated with ``register_menu_widget`` (by its path, and by ``name=``), a
class defined in the ``menu_widgets`` module of an installed app, or a path of
the new setting ``GT_MENU_WIDGETS``. Any other widget item is left out of the
menu with a warning in the ``djgentelella.menu`` log, and ``MenuItem.clean()``
(the admin) refuses it. To keep a widget of your own, decorate it, move it to
``<app>/menu_widgets.py`` or list its path in ``GT_MENU_WIDGETS``. See
``docs/source/menus.rst`` ("Custom Widgets").

**``{% get_settings %}`` escapes the values that are not HTML.** It printed
every ``GentelellaSettings`` value through ``mark_safe``, so a title with
markup was HTML in every page. Only the keys of ``GT_HTML_SETTINGS`` (by
default ``site_logo``) are printed as they are; any other is escaped,
keeping character references, so a value stored escaped by hand
(``Sales &lt;North&gt;``) shows the same text as before. A value that held
markup on purpose in another key shows it as text: add the key to
``GT_HTML_SETTINGS``. ``djgentelella.utils.get_settings_display(key,
site=None, default='')`` is what the tag prints; ``setting_allows_html``,
``html_settings`` and ``escape_setting`` are public. See
``docs/source/settings.rst`` ("Which values are HTML").

**Bootstrap with its own Popper.** The page header loads
``bootstrap.bundle.min.js`` instead of ``popper.min.js`` and
``bootstrap.min.js``, in the compressed bundle (``pylpfile.py``) and in the
separate files -- which did not load Popper at all. A dropdown (the Kanban's
"Move to", the menus) no longer dies with ``createPopper is not a function``
where ``window.Popper`` went missing. There is no global ``window.Popper``
any more: code of a project that used it loads ``vendors/bootstrap/
popper.min.js`` itself (``loaddevstatic`` still downloads it). The bundle is
built with ``python -m pylp`` (``make assets``), not committed.

**The list of a ``CheckboxSelectMultiple`` is ``ul.gt-check-list``.**
It was ``<ul class="gt-check ...">`` (and drew as one box). CSS or a script
that selected ``ul.gt-check`` selects ``ul.gt-check-list``; the boxes keep
``input.gt-check``. Adding a page in the admin validates its document for the
Site chosen and with the trust of the user adding it (before: global and
untrusted), so a page with a template ``html`` node is accepted there when
that user may publish templates, as ``gtdesigns_publish --user`` already
did. With ``GT_DESIGNS_RESOLVE_CONTEXT`` set, a page saved before it that
breaks the new rule stops resolving when it is served: validate the pages
(``gtdesigns_export`` + ``gtdesigns_publish``, or **Validate** in the admin)
before turning it on.

Fixes
""""""""

**Security: region components do not search through hidden columns.**
``cards``, ``calendar``, ``map``, ``tree``, ``timeline`` and ``metrics``
refused a filter on a column their ``column_conditions`` hide, but searched
every text column and ordered by default by any: a search could tell which
rows held a value the user may not see. They search and order only by the
visible columns (``query.apply_params_over``). Ordering a region by ``pk`` is
no longer a 400.

**What every page costs.** A warm page of the layout takes four queries (the
menu, the session and the user; ``PageQueriesTest``):

* ``get_settings`` cached only the keys it found: each key without a global
  row (``site_extracss``, ``sidebar_icon``, ``sidebar_title``,
  ``feedback_enabled``) cost a query on every page. A missing key is cached
  too, and forgotten when the setting is saved.
* ``{% pwa_head %}`` read the PWA settings twice; the rows of every Site are
  now one cached query (``PWA_SETTINGS_CACHE_KEY``), cleared on any save of
  ``GentelellaSettings``.
* ``gentelella/index.html`` ran ``get_or_create_permission_context`` for
  permissions of the demo (``demoapp``) on every visit: four lookups and a
  write on a ``GET`` in every project that used it. Its ``pre_head`` block is
  empty.
* ``djgentelella.theme.values``, imported by ``models.py``, imported Pillow at
  module level: about 4 MB per process. It is imported when a logo is
  validated.

**Design endpoints read less.** The data source and source-table rows skip the
second ``COUNT`` when there are no filters nor search; a region or a source
table reads its columns once per request; a map gets its popup template once
for all its points; a page of ``cards`` does not repeat the search to read its
rows.

**Pipelines of code know the Site.** ``PipelineFormMixin``,
``PipelineViewSetMixin`` and ``PipelinePageMixin`` built their pipeline
without the request's Site, so a ``page:`` branch to a page of that Site was
an ``ImproperlyConfigured`` (a 500).

**Wizard.** ``get_object()`` is called once per request (it was asked
dozens of times, a query each); validating a step no longer discards the
cleaned data of the others, so *Finish* validates each step once instead of
O(N²) times; *Previous* and a step link no longer answer a 500 when the
current step's own data makes it stop applying; and its pipelines are built
with the request's Site.

**Fewer reads in locking and flows.** ``OptimisticLockMixin.update`` read the
row four times, now twice. ``flow_detail`` evaluated every transition twice
(the buttons and the diagram): ``transition_buttons()`` and
``instance_diagram()`` take ``instance=`` and ``available=``. The global
search asks the ``GT_SEARCH_SOURCES`` hook once per request.

**The menu export keeps the drawn order.** ``export_tree`` wrote the children
by position while the menu draws them by id: an export followed by an import
changed the order. Children are exported by id.

**Validation instead of a 500.** A theme border radius such as ``²`` and a
malformed ``save_lov`` or ``save_page`` raised instead of reporting the error.

**The LOV popup and the Markdown preview drop late answers.** An answer that
arrived after a newer search, or after going back to *Write*, replaced the
newer one.

**Security: the parent of a design page is limited to the request's Site.**
A page about one object (``meta.parent``) of a model
exposed with a ``site_field``, and the API of its ``inline_object_management``
tables (and of their facets), reached an object of another Site by its pk: a
user with the (global) view permissions of both models read -- and, with the
add/change permissions, wrote -- that Site's details. ``parent_object()`` and
the inline viewsets now look the parent up among the rows of the request's
Site and the global ones, and answer 404 otherwise. An inline table also
accepts ``site_field`` now: its rows are those of the parent and of the Site,
and a new detail gets the Site.

**``list_filter`` with field names.** ``get_filters`` called
``field.is_instance(str)``, which ``str`` does not have, so a ``CRUDView``
whose ``list_filter`` named model fields raised ``AttributeError``.

**A hidden column is not a filter.** The filters of a ``CRUDView`` list drop
the fields over a column hidden by ``column_conditions`` (``price``,
``price__gte``...), as the list, the detail, the search and the ordering
already did: filtering by a column the user cannot see would tell its values
apart.

**Hiding a column does not reorder the rows.** ``CRUDMixin`` ordered by
``-pk`` when every ordering was over a hidden column, while a ``CRUDView``
list without ``Meta.ordering`` orders by ``pk``: a condition flipped the
order. It now leaves the queryset unordered and the view gives it its usual
order (``pk`` in ``CRUDView``, ``-pk`` in the designs).

**A page of a Site is served for its Site.** ``engine.resolve_page(page)``
resolved every page without a Site, while ``publishing.publish`` validates
the document for the Site it publishes in: a page that named something only
that Site has -- a ``flow:`` row link or a ``flow_kanban`` of a flow
published there -- was published and then answered 404. It now resolves the
page for ``page.site`` (a global page, as before, without one), and the Site
is part of its cache key.

**The ``model`` of a data source is deprecated as its project model.**
djgentelella reads ``source.project_model``; a ``DataSource`` subclass (or
any object) that only has ``model`` still works, with a
``DeprecationWarning``. Declare ``project_model`` (``None`` when its rows are
not rows of a model of the project). ``ModelDataSource`` and
``FunctionDataSource`` already do.

**``object_management`` no longer requires ``model`` and ``form`` in its
schema.** They are still required unless the node has a ``datasource`` (list
mode), but ``resolve()`` says so now (``"model is required (or a
"datasource"...)"``), not the JSON schema: a tool reading
``props_schema["required"]`` gets nothing there.

**The page's wrapper has its own attribute for the slug.** A design page
renders ``<div class="gtdesign-page" data-gtdesign="<root id>"
data-gtdesign-page="<slug>">``: ``data-gtdesign`` is always a node id, so a
node whose id is the slug of its page no longer makes
``[data-gtdesign="<slug>"]`` match two elements. A selector of the page by its
slug becomes ``[data-gtdesign-page="<slug>"]``.

**A generated grid without ``form`` is no longer taken for a read-only
one.** ``InteractiveGridBuild.list_only`` asks the data source
(``grid_can_edit``), not ``form is None``: an editable grid over a
``ModelDataSource`` whose build has no form (generated code passes
``form_class`` to ``grid_page_context``) came out read-only, without columns
nor actions.

**A page without the ``site_theme`` setting** (a database flushed by a test)
loads ``gentelella/css/custom.css`` instead of an empty ``<link
href="/static/?v=...">``.

**A source error that is also a ``ValidationError`` is a 503.** The
data source API and the endpoints of the design components (list and grid
over a data source, regions, metrics, chart, stat, facets) check
``DataSourceUnavailable`` before ``ValidationError``: a class that inherits
from both answers its 503/502/504, not a 400 (``datasources.base.api_error``).
``validate_params`` lets it through instead of reporting it as a problem of
the document.

**Test classes no longer hide each other.** ``tests/__init__.py``
imports every module with ``*``, and four test classes had the name of a
class of another module (``RegistryTests``, ``RenderEndpointTests``,
``SchemaTests``, ``PreviewTests``): 20 tests did not run. They are renamed,
and ``UniqueTestNames_Test`` fails on a repeated name, on a test case left out
of an ``__all__`` and on a ``*_Test.py`` that ``__init__.py`` does not import.

**Schemas that declared ``maxLength``/``maxItems`` are enforced.** The
validator ignored them: the ``prefix``/``suffix`` of a metric (8 characters),
the ``metrics`` list (12) and the ``center`` of a map (2 numbers) are now
checked when the document is validated.

**A design page in the menu with a trailing slash.** With the new
setting ``GT_MENU_DESIGN_PAGE_SLASH = True`` the link of a ``page:<path>``
item and of a reversed ``gt-design-page`` ends in ``/``
(``/designs/sales/clients/``), the URL a project that visits its pages with
the slash shows, so a breadcrumb or an "active item" that compares the link
with ``request.path`` matches. Off by default: the links stay as they were.
Both forms serve the page.

**Small fixes.** ``DataSource.__repr__`` was dead code inside
``source_column_map``: a source shows as ``<ModelDataSource name>``
again. ``MetricsComponent.render`` no longer repeats the access rule of
``RegionComponent.render``: both go through ``page_context``. Two test
helpers named ``DownSource`` are now ``TTMDownSource`` and
``W29DownSource``. The demo's SQLite test database is
``demo/test_db_<pid>.sqlite3``, one per process: the browser tests and
``make test`` can run at once in one checkout without destroying each
other's database (a killed run leaves its file; ``--keepdb`` keeps nothing
between runs).

**``CheckboxSelectMultiple`` draws one box per choice.** The
``gt-check`` class of its ``attrs`` reached the ``<ul>`` around the choices
too, which ``checks.css`` painted as one 13 px box: the choices spilled over
whatever came after it, in every layout. The list now gets ``gt-check-list``
(plus the other classes of ``attrs``) and ``gt-check`` stays on each
``<input>``; ``checks.css`` lays the list out one choice per line. A selector
that looked for ``ul.gt-check`` must look for ``ul.gt-check-list``.

**A metric card over every row says ``"period": "all"``.** It
answered ``period: ''``, as a card without a ``date_field``.

**A wizard's computation may set a field of a skipped step.** The
``fields`` of ``GTWizardView.finish_context`` were those of the steps that
applied, so the wizard's pipeline failed with ``PipelineError`` on a field of
a step skipped by its condition, although ``get_pipeline()`` had accepted it.

**The trailing slash of a design page in the menu stays opt-in.**
``GT_MENU_DESIGN_PAGE_SLASH`` remains off by default: turning it on changes
every link already drawn, and the projects on top of djgentelella assert the
links without it. ``docs/source/menus.rst`` says how to adopt it.

**The PWA's scope follows the script prefix.** Without
``GT_PWA_SCOPE``, the manifest's ``scope`` and ``start_url``, the service
worker's scope and its ``Service-Worker-Allowed`` header are the request's
script prefix (``SCRIPT_NAME``, ``FORCE_SCRIPT_NAME`` or the one a middleware
sets) instead of ``/``. A project served at the root sees no change; one
served under a prefix that wants the old scope sets ``GT_PWA_SCOPE = '/'``.

**The colours of a theme are stored normalized.** Saving a
``SiteTheme`` (or ``full_clean()``) writes each colour as ``#rrggbb`` in lower
case, so a theme saved as ``#AABBCC`` reads back ``#aabbcc``. Compare colours
case-insensitively, or through ``theme.values.normalize_color``.

**A page about another Site's object is a 404.** See the security fix
above: ``designs/<path>/<pk>`` and its inline APIs no longer reach an object of
another Site when its model was exposed with a ``site_field``. A project that
relied on it shares that object (empty ``site``) or exposes the model without
``site_field``.

**``Flow.dead_ends()`` of a flow without final activities is empty.** It
listed every state of a cyclic flow. Use ``Flow.is_endless()`` to warn about a
flow that never finishes.

0.7.1 (2026-11-15)
--------------------

Fixes
""""""""

**Saving a setting with a DatabaseCache and no cache table.** 0.7.0 forgets a
setting's cached value when the row is saved or deleted; with a
``DatabaseCache`` whose table was never created -- a test database, where
nobody runs ``createcachetable`` -- that query failed and took the save with
it, so loading any fixture with ``djgentelella.GentelellaSettings`` raised
``relation ... does not exist``. The failure is now logged as a warning
inside a savepoint (the surrounding transaction stays usable on PostgreSQL):
without the table there is nothing cached to forget.

**loaddevstatic survives a flaky CDN.** Downloads retry with backoff (5
attempts) and a timeout; a network error no longer kills its thread, which
silently left the rest of that thread's files undownloaded. A file assembled
from several parts (``tinymce-all.js``) is written only whole: a partial one
used to stay, and later runs skipped it because it existed. Downloads the
network still refuses are listed at the end and the command fails, instead of
going on to build a package without them.

**CRUD lists of a model without Meta.ordering are ordered.** They were
paginated unordered (Django's ``UnorderedObjectListWarning``), so a page could
repeat or skip rows. A classic CRUD now orders them by ``pk``; a design CRUD by
``-pk``, the default it already used when a condition hid a column -- now
showing or hiding a column no longer reorders the rows.

0.7.0 (2026-11-15)
--------------------

New features
""""""""""""""""""

**A flow engine, djgentelella.flows.** A ``Flow`` lists the states of a model
and the ``Transition`` between them, each with its permissions, a condition,
an optional form and actions: ``SetField``, ``Assign`` (a user or a group),
``Notify``, ``SendEmail`` (async_notification) and ``CallFunction``. Flows
live in ``<app>/gtflows.py``, registered from ``AppConfig.ready()`` so Celery
and management commands see them too. djgentelella serves an inbox per flow,
a page per object with its state, transitions and history, and the transition
pages; ``{% flow_status %}`` and ``{% flow_states %}`` put them in any page.
State lives in ``FlowInstance`` (any primary key type: integers, UUIDs, text
up to 255 characters), every run in ``FlowTransitionLog``. Running a
transition locks the object and checks it again, so two users cannot both
win a race; actions marked ``on_commit`` run only after the transaction
commits. Who reaches what is restrictive by default: everything with the
model's view permission, otherwise only what the user can act on or is
assigned to. Beyond that: ``on_enter``/``on_exit`` hooks per state and the
``pre_transition``/``post_transition`` signals; conditions that say why
(``TransitionBlocked``, shown on a disabled button); automatic transitions
(``auto=True``) as gateways; deadlines (``Deadline``) run by
``manage.py process_flow_timers`` or a Celery beat task; approvals by quorum
(``Approval(min=2)``); claim, release and reassign; bulk runs from the inbox;
and a server-side SVG diagram (``{% flow_diagram %}``). The demo shows five
flows at ``/flowdemos/`` (purchases, help desk, editorial review, leave
requests, countries), seeded by ``createdemo``. See ``docs/source/flows.rst``.

**Widgets picked from the model field.** ``djgentelella.forms.widgetmap``
holds the table of which djgentelella widget edits which model field, and
``gt_formfield_callback`` applies it to a ModelForm through
``Meta.formfield_callback``: dates get ``DateInput``, booleans ``YesNoInput``,
relations to a ``TreeNode`` ``TreeSelect`` with the tree form field, and so on;
``Meta.widgets`` still wins. djgentelella-editor reads the same table. See
``docs/source/forms.rst``.

**Signing service token.** ``RemoteSignerClient`` now sends
``Authorization: Bearer <FIRMADOR_TOKEN>`` on every call to the signing
service (sign, validate and complete), so it can talk to a firmador_api
deployed with ``API_TOKEN``. The setting is optional: when it is unset or
empty no header is sent and behaviour is unchanged.

**Signing service replica affinity.** firmador_api keeps each document in
memory between ``firme`` and ``completa``, so with several replicas the second
call must reach the instance that served the first. When the signer runs with
``IS_DISTRIBUTED=true`` its ``firme`` answer carries that instance's URL in
``hostname``; the client now keeps it server side in the Django cache (keyed by
document id, ``FIRMADOR_AFFINITY_TTL`` seconds, default 3600) and sends
``completa`` there. Only a bare ``http(s)://host[:port]`` is accepted, and it
never goes through the browser. Without it -- a single signer, or
``FIRMADOR_AFFINITY = False`` -- ``FIRMADOR_SIGN_COMPLETE`` is used as before.
Use a cache shared by all workers (database, Redis) if signing can hop between
processes.

**Leaflet map widgets.** Two widgets sharing one JavaScript engine
(``gentelella/js/base/maplib.js``):

* :class:`~djgentelella.widgets.maps.MapPointInput` asks the user for a single
  GPS point -- click, marker drag, "use my location", address search or
  ``based_fields`` geocoding from other fields. It stores the plain string
  ``"latitude,longitude"``, so **no GeoDjango, GDAL or PostGIS is needed** and
  it works on SQLite. ``djgentelella.fields.maps`` adds the matching
  ``GTPointField`` model field (with a proper ``deconstruct()``) and
  ``GTPointFormField``.
* ``DJMap`` draws many points fetched from an API, the sibling of ``DJGraph``:
  marker popups, per-layer clustering, a heatmap and a layer switcher. Subclass
  :class:`~djgentelella.views.maps.BaseMapView` in ``<app>/gtmaps.py`` and
  include ``gentelella/widgets/djmap.html``. Filters use the same
  ``#selector`` / ``{funcName}`` ``data-*`` syntax as the chart widget.

Leaflet is always loaded. Marker clustering and the heatmap come with the new
``use_maps`` define in ``DEFAULT_JS_IMPORTS``; without it maps still work, with
clustered layers falling back to plain layer groups.

Four new bundles are produced by ``pylp``:
``djgentelella.maps.vendors.min.{js,css}`` and
``djgentelella.maps.plugins.min.{js,css}``. They are emitted **after** the
readonly bundle on purpose -- storymapjs embeds Leaflet 0.7.7 and assigns it to
``window.L``, so the reverse order silently downgrades every map.

See ``docs/source/widgets/maps.rst``.

**Two generic javascript components.** Both are classes concatenated into
``base.js`` by ``createbasejs``, with a stylesheet of their own linked from
``gentelella/statics/stylesheets.html``.

* ``PositionsGrid`` (``gentelella/js/base/positionsgrid.js``) draws a matrix of
  rows and cells where each cell holds zero or more opaque items. **Rows are
  irregular on purpose**: a row of two cells is half the width of a row of four,
  cells stay left aligned and nothing is padded out to a rectangle, because the
  shape is the host's data and not a grid the widget imposes. The widget keeps
  no state of its own and serialises nothing -- every mutation goes out through
  a handler that resolves with the new state and the grid repaints with that, so
  a rejected handler leaves the screen showing exactly what the server last
  confirmed and fires ``pg:error``. Moving an item is two taps (pick, then
  destination), not a drag, so it works on a phone and from the keyboard; the
  desktop drag is the same code path.
* ``BreadcrumbNav`` (``gentelella/js/base/breadcrumbnav.js``) fills the
  ``{% block breadcrumbs %}`` of ``base.html`` and ``plain.html``, which had been
  empty since the theme was ported. A view that puts ``breadcrumbs`` in its
  context now gets the path server-rendered from
  ``gentelella/blocks/breadcrumb.html``; pages that do not are unaffected, the
  include renders nothing.

The demo warehouse at ``/positionsgrid_view`` wires all seven handlers to real
endpoints and refuses to delete a row that still holds boxes, which is the only
way to see the rejection path on screen.

See ``docs/source/appwidgets/positionsgrid.rst``.

**The history knows what an entry was about.** A ``LogEntry`` only points at
the object that changed, so an application that wants "everything that happened
in this laboratory" had nowhere to hang that context and ended up matching on
the translated ``change_message``. The new ``HistoryRelation`` model (migration
``0019``) attaches any number of objects to one log entry through a generic
foreign key, plus a ``data`` JSONField per relation:

* ``add_log()`` takes ``related_objects=`` (model instances, or
  ``(instance, data)`` tuples -- a bare pk raises ``ValueError``, because a pk
  alone does not say which model it belongs to) and ``extra=``, and it now
  *returns* the ``LogEntry`` it created. A custom ``change_message`` on a
  DELETE is no longer overwritten.
* Entries logged with no authenticated user go to the username in the new
  ``GT_HISTORY_ANONYMOUS_USERNAME`` setting, so a project can point them at its
  own sentinel account instead of losing the entry.
* ``HistoryViewSet`` gained a ``scope_queryset()`` hook, the
  ``related_contenttype`` / ``related_id`` filters and an ``?extra={"k": v}``
  filter that chains one to many keys against the *same* relation row (and
  works on SQLite). Its ``recordsTotal`` is now the scoped universe: the global
  count leaked the platform's volume to every tenant. A project without
  ``GT_HISTORY_ALLOWED_MODELS`` no longer hits a ``TypeError``.
* ``BaseViewSetWithLogs`` was repaired throughout: ``models_log`` replaces the
  attribute that never existed, ``perform_destroy`` passes ``delete(user=)`` for
  ``DeletedWithTrash`` models, ``perform_update`` resolves fields by ``source``,
  and ``get_log_related_objects()`` / ``get_log_extra()`` let a subclass add
  context without overriding the whole method. With ``log_request_metadata``
  the browser, IP, method and path are captured on their own.

**The trash records the context of a deletion, and can be scoped.**
``TrashRelation`` (migration ``0020``) is to ``Trash`` what ``HistoryRelation``
is to ``LogEntry``: ``DeletedWithTrash.delete(..., related_objects=[...])`` --
and the queryset-level ``delete(user=, related_objects=)`` -- record which
objects the deletion belonged to. The first deletion wins: re-deleting
something already in the trash keeps the standing context, and a restore
cascades it away so the next deletion records afresh.

``TrashViewSet`` mirrors the history viewset: the same
``related_contenttype`` / ``related_id`` filters, the same ``scope_queryset()``
hook, and a scoped ``recordsTotal``. Because ``restore`` and ``destroy``
resolve through ``get_object()``, the hook narrows those actions too, which is
what a multi-tenant project needs to keep one tenant out of another's trash.
Restore now respects scoped subclasses, an entry whose object is gone answers
``410`` instead of failing, its permission check is aligned with
``change_trash``, and entries can be filtered by ``deleted_by``.

Both models are registered in the admin. ``djgentelella.utils
.contenttypes_from_labels`` is the single place where ``app_label.model``
strings become ContentTypes, shared by history and trash.

See ``docs/source/history.rst`` and ``docs/source/trash.rst``.

**Menus and settings per Site.** One installation can serve several
applications, each one a ``django.contrib.sites`` Site with its own menus and
settings. ``MenuItem.site`` and ``GentelellaSettings.site`` are optional
foreign keys: empty is global, and the value of the current Site wins over the
global one. ``djgentelella.sites`` gives ``get_current_site(request)``
(``request.site`` when a middleware set it, else the Site of the host, else
``None``) and ``site_q(site)``. The menu tags hide the items of other Sites at
every level, even under a global parent, and an item of the Site with the same
``url_name`` and ``category`` as a global one replaces it (with a
placeholder ``url_name`` -- ``''``, ``'/'``, ``'#'`` -- the ``title`` must
match too).
``get_settings(key, site=None)`` and ``set_settings(key, value, site=None)``
fall back to the global value, the cache is kept per ``(key, site)``, and
``{% get_settings %}`` takes the Site of the request. Any ORM save or delete of
a setting, the admin included, now clears its cached value, also in the
key and Site it had before the save. The admin shows
the Site and filters by it, and ``demomenu --with-site`` builds a second Site.
See ``docs/source/sites.rst``.

**Design documents served as pages, djgentelella.designs.** A new app (label
``gtdesigns``, extra ``[designs]`` for nh3) loads the JSON designs
djgentelella-editor writes, validates them and renders them live inside
``gentelella/base.html``, without generating code or installing the editor.
``python manage.py gtdesigns_publish design.json [--site] [--path] [--user]``
validates and saves a ``Page`` (optional Site, path, document, hash), served
at ``designs/<path>`` by the current Site with the global page as fallback,
honouring ``is_published`` and the page's permissions; ``gtdesigns_export``
writes it back. Node types are ``RuntimeComponent`` subclasses registered from
each app's ``gtdesigns.py`` or ``GT_DESIGN_COMPONENTS``; ``page``, ``row``,
``col`` and ``html`` ship built in, and a node may serve DRF viewsets under
``gtapis/designs/<page>/<node>/``. A design can only use the models an app
exposed with ``expose()``; its ``html`` is cleaned to an allow list and is not
a Django template unless ``GT_DESIGNS_ALLOW_TEMPLATES`` is on and the
publisher holds ``gtdesigns.publish_template`` (likewise ``assets.js`` with
``GT_DESIGNS_ALLOW_JS`` and ``gtdesigns.publish_js``). The format, its
validator and the form builder moved here from the editor. See
``docs/source/designs.rst``.

**Data sources, djgentelella.datasources.** A ``DataSource`` names the rows,
the columns and the permissions of a report, in Python where Oracle APEX
writes a ``SELECT``: ``ModelDataSource`` derives the columns from a model
(with ``fields``, ``exclude``, ``perms`` and an optional ``site_field``),
``FunctionDataSource`` wraps a function that returns a queryset. They live in
``<app>/gtdatasources.py``. A JSON parameter document -- the one a saved
report will store -- drives the query engine: filters checked against each
column's kind (``eq`` to ``date_period``), search (full-text on PostgreSQL,
``icontains`` elsewhere), ordering, ``group_by`` with aggregates, a pivot
built with ``Case/When``, facets that count with every filter but their own,
and highlights. The results export to CSV (streamed), JSON, XLSX (openpyxl,
the new ``export`` extra, with totals and conditional formatting) and PDF
(xhtml2pdf, the new ``pdf`` extra, with a repeated header and page numbers);
``EXPORTERS`` takes more formats. Everything is served under
``gtapis/datasources/<name>/`` and consumed by new widgets: a facets panel, a
chips version, an export menu and ``gtCreateDataSourceTable``. The demo shows
them at ``/datasources/``. Add ``'djgentelella.datasources'`` to
``INSTALLED_APPS`` to use it. See ``docs/source/datasources.rst``.
A source without ``perms`` needs an authenticated user (``perms=[]`` makes it
public); JSON and XLSX exports stop at ``GT_DATASOURCE_EXPORT_MAX_ROWS``
(50000) and CSV/XLSX cells never run as formulas. ``gtCreateDataSourceTable``
escapes every cell and column title (``fk``/``m2m`` names included), XLSX drops
the control characters XML does not allow, a POST body that is not a JSON
object is a 400, and ``FunctionDataSource`` checks the permission before
calling its function (``model=`` gives it an empty queryset to return).

**Flows v2: activities, variables, versions and a task inbox.** Besides
states and transitions, a flow now has the activities ``Switch`` (a branch by
condition), ``Wait`` (a delay, a date in the variables or a signal sent with
``flow.signal(obj, name, data)``), ``Parallel``/``Join`` (all branches or the
first N), ``Subflow``, ``HumanTask`` and ``ActionActivity``. Instances keep
``variables`` (JSON) that conditions read and actions, transition forms,
signals and tasks write, and can be suspended, resumed, terminated and
retried: an automatic activity that fails leaves the instance in error, and
``retry`` enters it again. Flows can be written in JSON
(``djgentelella/flows/schema_v2.json``) and loaded at runtime into a
``FlowDefinition`` (``manage.py gtflows_publish``), by Site; each publication
is a version, and an instance stays with the version it started with.
Actions are registered by name with a JSON Schema of their props
(``action_from_json``), with the new ``set_variable``, ``create_task`` and
``start_flow``. Human tasks (``Task``, ``TaskComment``, ``TaskHistory``)
are claimed, released, delegated, asked and answered for information and
completed with an outcome, with priority, due date and expiry that escalates
or decides; ``flows/inbox/`` is one inbox for the tasks of the user and their
groups, filtered by flow, priority, state and due date. The diagram of an
instance marks its activities under way, done and failed, and
``process_flow_timers`` (or ``timers.process_due()``) runs deadlines, waits
and task expiries. New signals ``task_created``, ``task_completed`` and
``flow_state_changed``. The demo adds an expense approval written both in
Python and in JSON. See ``docs/source/flows.rst``.

**Dynamic actions and cascading lists of values.** A form declares
``dynamic_actions = [When('tipo').equals('empresa').show('razon_social'), ...]``
(``djgentelella.forms.dynamic``) and a small runtime in ``base.js`` runs them:
triggers ``changes``, ``on_load``, ``equals``, ``not_equals``, ``in_``, ``gt``,
``lt``, ``is_empty`` and ``is_checked``; actions ``show``/``hide``,
``enable``/``disable``, ``require``, ``set_value`` (a constant, another field or
a form method run on the server), ``refresh``, ``confirm``,
``add_class``/``remove_class`` and ``call`` (a function registered with
``document.gtdynamic.register``). Conditions are re-evaluated on every change
and undo their reversible actions when they stop holding. GTForm emits the
rules in every render; a form without them renders the same html as before.
They work in formsets and in ObjectCRUD modals. ``set_value(server=...)`` goes
through ``gtapis/dynamic/`` with a reference signed by ``django.core.signing``,
and only methods declared in the class rules can be called; the token expires
after ``GT_DYNAMIC_ACTIONS_MAX_AGE`` seconds (12 hours), is bound to the user
of ``form.request`` when the form has one, and
``Form.dynamic_actions_has_permission(request, method)`` (authentication plus
``dynamic_actions_permissions`` by default) decides who may run it. Lists of values
are registered with ``@register_lov(name, depends_on=[...], perms=[...])`` in
``<app>/gtlovs.py``, served at ``gtapis/lov/<name>/`` (login required by
default), edited with ``LOVSelect``/``LOVSelectMultiple`` and validated with
``LOVChoiceField``/``LOVMultipleChoiceField`` against the parent values the form
received; a malformed parent value (``?pais=abc``) makes the LOV empty
instead of a 500. The demo shows country -> province -> canton, a total computed on the
server and a confirmation at ``/dynamic_actions/``. Run ``createbasejs`` to
rebuild ``base.js``. See ``docs/source/dynamic_actions.rst`` and
``docs/source/lov.rst``.

**Wave 1 integrated.** The stages share one Site rule: designs, data sources
and flows resolve the current Site with ``djgentelella.sites`` (``request.site``,
else the Site of the host, never ``SITE_ID``), so the local fallbacks of
``djgentelella.designs`` (``designs/sites.py``, removed) and
``djgentelella.datasources`` are gone, and ``ActionContext`` takes its Site
from the request the same way. With ``djgentelella.datasources`` installed the
task inbox is the data source ``flows.tasks``, with facets and exports. The flow
definitions are validated by ``djgentelella.designs.jsonschema``, no longer a
copy of it.

**Authorization schemes, conditions and feature flags,
djgentelella.authorization.** Access rules are Python functions with a name,
``@authorization('es_supervisor')`` in ``<app>/gtauth.py`` (autodiscovered),
checked with ``check_authorization(name, request, obj=None)`` and cached on the
request (``cache=False`` opts out). A condition is JSON --
``perm``, ``auth``, ``group``, ``setting`` (``equals``/``in``), ``flag``,
``user_attr`` (only ``is_staff``, ``is_superuser``, ``is_authenticated``),
``all``, ``any`` and ``not`` -- evaluated by ``evaluate_condition`` (``None``
holds; an invalid one or an unknown authorization is false, and logged) and
checked by ``validate_condition``, which returns ``(path, message)`` errors.
It works in DRF (``ConditionPermission`` with ``condition`` or
``conditions_by_action``, restrictive by default), in views
(``ConditionRequiredMixin``, ``condition_required``), in templates
(``{% if_condition %}``, ``{% if_flag %}``, ``request|authorized:"name"``,
library ``gtauthorization``), in menus (the new ``MenuItem.condition``, migration
``0023_menuitem_condition``; items without one behave as before), in design
nodes (``props.condition`` or ``meta.condition``: the engine leaves out the
node, its children and its endpoints) and in flows (the authorization conditions are no
longer behind an ``ImportError``; outside a request they are evaluated for the
run's user and Site through ``ConditionRequest``). Feature flags are settings
with the ``flag.`` prefix and the Site rule: ``flag_enabled(name, request)``,
``set_flag(name, value, site=None)``, and a *Feature flags* page in the
settings admin with a toggle per Site. ``GT_SITE_GROUPS_RESOLVER`` decides
which groups of a user count on a Site (all of them by default). See
``docs/source/authorization.rst``.

**Data components of djgentelella.designs.** Designs get the editor's
components with data, served with no generated code: ``object_management``
(a DataTable with create, update, detail and delete modals over an
``AuthAllPermBaseObjectManagement``), ``inline_object_management`` (the
children of the page's parent object, at ``designs/<path>/<parent pk>``),
``chart`` (Chart.js, an aggregate of a model or a data source grouped by a
field or a date period), ``stat`` (one number, optionally against the previous
period), ``crud_classic`` (``CRUDView``, its list in the page and its pages
under the node's endpoint) and the new ``facets`` (``GTFacets`` filtering a
table of the page). Their builds hold data only; serializers, filtersets and
viewsets are made at runtime (``djgentelella.designs.factories``) and cached
by page hash and node. Tables can notify by email or in-app notice on create,
update and delete. Every endpoint checks ``AllPermissionByAction``, only
exposed models and fields are accepted, and ``preview=True`` renders sample
rows with empty querysets. The demo gets the catalogue models and three
designs adapted from the editor's (``demoapp/gtdesign/``). See "Data
components" in ``docs/source/designs.rst``.

**Conditions on the data components of the designs.** A condition of
``djgentelella.authorization`` on a table, inline table, chart, stat, classic
CRUD or facets node -- or on one of its ancestors -- leaves it out of the page
and answers 404 at every one of its endpoints, the page of one object
(``designs/<path>/<pk>``) included. A component may name the nodes it works on
(``depends_on(build)``): it then exists only where they do, so a facets panel
goes with the table it filters. ``GTDataSourceState.query`` adds the slash after
the endpoint (``.../facets/?...``), which the data source API takes either way
and the design router requires; the design facets no longer patch it.

**Uploads per user, cleaned design CSS and a complete Spanish catalog.**
``UserFileChunkedUpload`` and ``UserFileInput`` take a chunked upload only when
it belongs to their user and finished (``COMPLETE``); any other token gives
``None`` and deletes nothing. A form gets the user to them with
``UserScopedUploadsMixin`` (``Form(data, user=...)`` or ``request=...``). The
generic ``FileChunkedUpload`` and ``FileInput`` stay as they were, on purpose:
who attaches or deletes a document need not be who uploaded it; both gained the
``get_upload``/``upload_value`` hooks and give ``None`` on a malformed token
instead of a 500. A stored file whose name holds quotes or ``</script>`` no
longer breaks the widget's JSON. The ``assets.css`` of a design is cleaned
(``@import``, ``expression()``, ``-moz-binding``, ``behavior`` and
``javascript:`` URLs, also behind comments and escapes) unless the page may
serve ``assets.js``; ``djgentelella.designs.css.clean_css`` does it. The node
endpoints of a design apply the Site rule to the page pk too: a page of
another Site, or a global page that the current Site overrides at the same
path, is a 404. The ``es`` catalogs (django and djangojs) translate every
string of djgentelella, including facets, the task inbox, flows, designs,
data sources and flags (``Flitros`` is ``Filtros`` at last), and the task
outcomes are shown through the ``outcome_label`` filter of ``gtflows``.
In its review round: ``clean_css`` repeats until a pass changes nothing, so
removing a rule no longer joins ``@im@import x;port`` into an ``@import``; the
upload widgets (``FileChunkedUpload``, ``FileInput``, ``PDFViewerWidget``) write
the file name as text, never as HTML; ``UserFileChunkedUpload(keep_upload=True)``
gives the form the ``ChunkedUpload`` itself without deleting it;
``UserScopedUploadsMixin`` takes ``self.user`` (or ``self.request.user``) of a
form that keeps its own and binds the subwidgets of a ``MultiWidget``. Dotted
paths read from settings (``GT_DESIGN_COMPONENTS``, ``GT_SITE_GROUPS_RESOLVER``)
stay outside the flow allowlist, which only restricts paths that come from
data.

**Public hooks of the data sources.** ``query.validate_params(source,
request, params, strict=False)`` checks a parameter document without running
it and returns ``(clean, errors)`` with every problem and its JSON path
(``$.aggregates[1]: ...``); ``group_expr`` and ``aggregate_expr`` are the
public names of the checks of one entry (``_group_expr`` and
``_aggregate_expr`` still work). ``coerce_value`` refuses ``NaN``, the
infinities and decimals past the size of their column (``Column.max_digits``
and ``decimal_places``, taken from the model) with a ``ValidationError``, so
the API answers 400 instead of failing in the database; a list as a period or
an aggregate function is a 400 too. ``EXPORTER_RESOLVERS``
(``register_exporter_resolver``) add formats per request, ``(request) ->
{fmt: exporter}``: ``available_formats(request)`` is what the API accepts, the
source endpoint lists and the export menu and ``gtCreateDataSourceTable``
offer by default. ``GT_DATASOURCE_EXPORT_HANDLER`` ``(request, source, params,
fmt) -> HttpResponse | None`` takes over the export endpoint when it answers
(a background job for a large export) and lets it run when it returns
``None``. See ``docs/source/datasources.rst``.

**Public hooks of the flows.** A ``human_task`` takes a ``form``: a form
registered with ``@register_task_form`` (in JSON, its name; only registered
forms are found), shown on the task page, validated (400 with the errors) and
written to the variables. ``registered_actions()``,
``registered_conditions()``, ``registered_task_forms()``,
``registered_flows(published=False)``, ``activity_arguments()``,
``catalogue()``, ``COMMON`` and ``ARGUMENTS`` describe the registries as
JSON, for a designer. ``GT_FLOWS_ACTION_POLICY`` and ``ActionContext(...,
policy=...)`` are asked before each action runs; a refusal is logged, sends
``action_blocked`` and raises ``ActionNotAllowed``. ``ActionContext(...,
render_context=fn)`` (``context.render_context()``) is the context the texts
of the actions render with. ``ConditionRequest(user, site)`` is documented as
the way to evaluate conditions on behalf of a user outside a request; it now
takes a Site id and carries empty ``GET``/``POST``/``META``. See
``docs/source/flows.rst`` and ``docs/source/authorization.rst``.

**Deleting the object of a JSON flow no longer leaves its tasks open.** The
cleanup of an object's flow instances was only connected in a process that had
built the flow, so a shell, a command or a fresh worker deleting the object
left its tasks in the inbox, and completing one was a 500 (``DoesNotExist``).
Now every model a ``FlowDefinition`` runs on is watched from the first database
connection of a process, the open tasks are cancelled (with their history) and
kept as tasks of no flow, and a task whose object is gone anyway is cancelled
with a message when someone completes it, or when it falls due. "Gone" is
checked with the model's ``_base_manager``, so an object a default manager
hides (soft delete, archived, by Site) never loses its instance or its log.
The export endpoint checks the parameters with ``validate_params`` before
``GT_DATASOURCE_EXPORT_HANDLER`` gets them; an action policy that raises gives
the user a generic reason (``ActionNotAllowed('...')`` keeps its own);
``ConditionRequest(site=<id of no Site>)`` raises ``ValueError`` instead of
taking the global scope; ``gtCreateDataSourceTable`` lists ``csv``, ``xlsx``,
``json``, ``pdf`` first.

**Public hooks of the design engine.** ``ResolveContext`` gets
``check_permissions(path, perms)`` and ``lookups(model)``, and
``exposure(label)`` without a path only asks; the components with data and
the table notifications go through them, so a context of its own changes what
a design may use. ``engine.resolve()`` takes a ``context`` (a ``ResolveContext``
subclass or instance) and ``components`` (instead of the registry), with its
old signature unchanged. Row links reach a flow (``flow:<name>``, or
``flow:<name>:<transition>``) and take a condition; tables and classic CRUDs
take ``column_conditions`` (a hidden column leaves the page and the API: rows,
detail, search, filters, ordering, facets) and ``action_conditions`` (a
refused action is a 403). A hidden column is not read nor written by an
update, and the default ordering does not follow it. The conditions of a page
about one object are evaluated with that object where the node's endpoints
carry it (an inline table and its facets); the other nodes are evaluated
without it on the page as in their API. ``engine.render()`` renders with a
copy (``ResolveContext.copy_for()``) of the context instance the page was
resolved with. A component with ``facets_target`` and
``facets_source()`` can be the target of a ``facets`` panel.
``GT_DESIGNS_PAGE_CONTEXT`` and ``GT_DESIGNS_BASE_TEMPLATE`` give the design
pages the theme, breadcrumbs or layout of whatever mounts them. See
"Extending the engine" in ``docs/source/designs.rst``.

**The form of a human task goes through the flow allowlist.** In a JSON
flow, ``human_task.form`` is a name registered with ``register_task_form`` or
the dotted path of a form class that
``GT_FLOWS_ALLOWED_CALLABLES`` (or ``register_callable``) allows;
``get_task_form`` is still the one place a name becomes a class.
``publish_definition`` refuses any other name (``$.states[i].form``,
``taskforms.validate_task_forms``); a stored document still loads, and its
``human_task`` refuses to create the task, logged and with the activity in
error, until the name is allowed.

**Configurable alerts, djgentelella.alerts.** An app registers a process
(``register_alert_process``: its evaluator, the triggers it accepts, who
manages its rules) and the project makes ``AbstractAlertRule`` and
``AbstractAlertEvent`` concrete (``GT_ALERTS_RULE_MODEL``). ``fire_alert``
records the event -- once per ``dedupe_key`` while it is open, optionally
repeated with ``renotify_after`` -- and notifies through pluggable channels:
email from an async_notification template (with a ``sender`` hook), the
notification bell, or any ``AlertChannel`` a project registers.
``resolve_alert`` closes it with the evidence (a generic foreign key) and
tells the channels. Triggers are registered in code with their threshold
fields (``absolute``, ``percent``, ``missing``, ``due``), and
``fire_due_alert`` covers the "calibration coming due" case: ahead of the date,
on it, and repeatedly while overdue. ``run_alert_rules`` evaluates a process
from cron or the Celery task. Abstract models only: no app, no migration. See
``docs/source/alerts.rst``.

**Who may add to a catalog (#116).** ``SelectWithAdd``,
``SelectMultipleAdd``, ``TreeSelectWithAdd``, ``TreeSelectMultipleWithAdd``
and ``FilteredSelectMultiple`` take ``add_perms``: without those permissions
the user gets the plain select, with no add button and no modal. The user
comes from the form through ``UserBoundWidgetsMixin`` -- the former
``UserScopedUploadsMixin``, a name that still works -- and with ``add_perms``
and no user the button is hidden. Without ``add_perms`` nothing changes. The
blog's entry form uses it for its categories. The add button of the tree
widgets, still on Bootstrap 4's ``data-toggle``, opens its modal again. See
``docs/source/widgets/select_widgets.rst``.

**Chart datasets carry every Chart.js option.** A dataset of
``get_datasets`` keeps the keys ``DataSetSerializer`` does not declare
(``borderDash``, ``pointRadius``, ``pointBackgroundColor``, ``pointStyle``,
``tension``, ``spanGaps``, ``yAxisID``, ``order``, ``hidden``...) instead of
dropping them silently, and ``data`` takes ``None`` for a gap: dashed limits
and points coloured one by one, as a control chart needs. The same goes for
pie and scatter datasets. A dataset with the declared keys alone serializes as
before. See "Dataset options" in ``docs/source/appwidgets/charts.rst``.

**djgentelella.serializers.DataTableSerializer.** The envelope DataTables
expects (``draw``, ``recordsTotal``, ``recordsFiltered``, ``data``); subclass
it and declare ``data`` with the row serializer. The history, trash,
notification and async_notification tables use it.

Backwards incompatible
""""""""""""""""""""""""

**djgentelella.flows is an app of its own, and needs django.contrib.sites.**
Add ``'django.contrib.sites'`` and ``'djgentelella.flows'`` to
``INSTALLED_APPS`` (and ``SITE_ID``) and migrate. Its models live in
``djgentelella.flows.models`` (app label ``gtflows``) with their own
migrations. Because the engine was never released, its history was rewritten
instead of migrated: ``djgentelella/migrations/0021_flows.py`` no longer
creates ``FlowInstance``, ``FlowTransitionLog`` and ``FlowVote`` -- it is kept,
empty, so the migrations after it hold -- and a database that applied the old
one keeps three orphan ``djgentelella_flow*`` tables to drop by hand.
Conditions now get the run's context (``condition(context)``, with
``context.obj``, ``context.user``, ``context.variables``) instead of
``(obj, user)``. ``Approval`` and ``FlowVote`` are gone: a quorum is a
``HumanTask(each=True, min=2)``, one task per approver. The ``{% load gtflows
%}`` tags and the ``process_flow_timers`` command moved into the app, the
Celery task is ``djgentelella.flows.tasks.process_flow_timers_task`` still,
and ``reassign_perms`` defaults to ``gtflows.change_flowinstance``.

**The help palette showed its own template placeholders.** The panel builds
each entry by cloning a hidden prototype block and swapping ``$title`` and
``$text`` into it. That block was hidden with ``class="hidden"`` -- a Bootstrap
3 utility, dropped in Bootstrap 4, defined neither by Bootstrap 5 nor anywhere
in this project -- so it was not hidden at all, and the raw ``$title``,
``$byline`` and ``$text`` sat at the bottom of every help panel. It is
``d-none`` now.

The palette had no tests, because it only renders once a ``MenuItem`` points at
it and the demo's menu comes from a management command the suite never runs.
Five browser tests now create that menu item and cover the panel opening, the
prototype staying invisible while keeping its placeholders, a stored entry
listed with its text, and the question mark landing on the label of the field
it documents.

**Two fixes for forms that live in a modal.**

*TinyMCE arrived empty at the server.* The editor writes its content back into
the ``<textarea>`` only when the form is really submitted, through a hook it
installs on the form element. A modal is not submitted -- its javascript reads
the fields and posts JSON -- so the textarea still held whatever it had when
the editor booted, usually nothing, and the field came back *"this field cannot
be blank"* over a box with visible text in it. ``obtainFormAsJSON()`` now
flushes every editor in the form before reading it.

*And it arrived empty at the editor.* The other direction named two widgets by
hand, ``EditorTinymce`` and ``TextareaWysiwyg``, so editing an object whose
field used any other editor widget -- ``VoiceEditorTinymce``, or one a project
subclasses -- wrote the stored value into the hidden textarea and left the
editor blank over data that was there; saving then wiped it. It asks TinyMCE
whether it manages the element instead, which covers every variant.

Both faults reached ``async_notification`` as well -- every message field there
is an ``EmailEditorTinymce`` inside a create/update modal -- so four browser
tests now cover that screen too: the editor's content reaching the server, a
stored message reaching the editor, the preview button, and the widget keeping
``data-widget="EditorTinymce"`` so the shared initialiser runs. Unlike the
compose test, which was the module's only browser coverage, they need no
MailHog.

**``ChunkedUploadBaseView.login_required``.** The upload views refused every
anonymous request with a 403 baked into ``check_permissions()``, so a public
form with a file on it could not work and there was nothing to override short
of rewriting the method. It is a class attribute now. **The default is still
True** -- an open upload endpoint is somewhere for anyone to park files -- and a
project that wants otherwise subclasses:

.. code:: python

    class PublicUpload(ChunkedUploadView):
        login_required = False

Note that an anonymous upload cannot be scoped to its owner, so its 32
character ``upload_id`` is the only thing protecting a partial upload;
``get_max_bytes()`` still caps the size.

**The upload widgets got their missing half.** Their file input has always been
transparent -- that is what makes the whole area a click target and a drop
target -- but nothing was ever drawn underneath, so an empty widget rendered as
a blank white box with no label, no button and no hint that it could be clicked
at all. ``gentelella/css/fileupload.css`` draws that surface, and it is a
backdrop behind the input rather than a replacement for it, so no javascript
changed. The same file gives the widgets a real progress bar (the only sign an
upload was running used to be a percentage inside a 3 rem chip), makes the
download control neutral instead of ``bg-danger`` -- a red button, in a palette
where red is how deletion is spelled, for the one control that only reads --
and turns the delete row into a labelled checkbox that goes red only once it is
armed. ``PDFViewerWidget`` gets the same treatment. Colours and the accent are
``--gt-upload-*`` custom properties.

**``FileChunkedUpload`` on a model ``FileField`` now has tests, and the demo
can actually delete.** The widget already resolved the upload token into the
uploaded file (``value_from_datadict``) and rendered a file that came from the
database (``format_value``), so a ``FileField`` needs nothing but
``widget=FileChunkedUpload`` -- but none of that round trip was covered. Four
browser tests now walk it: the upload is saved into the model field byte for
byte, reopening the record shows the stored file with its download link, saving
without touching it keeps the file, and ticking *delete this file* clears it.

That last one exposed a demo bug: ``ChunkedUploadItem.fileexample`` was
declared without ``blank=True``, so the delete checkbox the widget ships could
only ever produce *"This field cannot be blank"* on submit. Any model that
offers that checkbox needs a field that allows blank; the demo's does now
(migration ``0028``).

**The chunked upload is ours now: blueimp jQuery-File-Upload is gone.** The
upload group was four vendored files; it is one. ``jquery.fileupload.min.js``
is replaced by ``gentelella/js/base/chunkedupload.js``, which speaks the
protocol ``chunked_upload/views.py`` already defined -- slice, POST with a
``Content-Range``, thread the ``upload_id``, then hand over the checksum -- in
about 130 lines of ``fetch``. With it go ``jquery.ui.widget.min.js``, which was
only there because blueimp is built on the jQuery UI widget factory, and
``jquery.iframe-transport.min.js``, a fallback for browsers with no XHR file
upload, meaning IE9. ``spark-md5`` stays: it hashes a file incrementally, which
SubtleCrypto cannot do, and the alternative is holding the whole upload in
memory to checksum it.

``FileChunkedUpload`` and ``PDFViewerWidget`` had a copy each of the same
uploader and the same md5 helper; both now call the shared one.

**This fixes a race that could reject a good upload.** The checksum was
computed in the background while the upload ran, so a small file on a fast
connection finished first and the completion request went out with an empty
``md5`` -- the server answers *"Both 'upload_id' and 'md5' are required"*, and
the file is lost after transferring fine. The hash is now awaited before the
first slice is sent.

Uploads had no browser test at all, which for a widget that is entirely
javascript meant none. Four now push a real 240 kB file through a real browser
and compare what landed on the server byte for byte, check that a small file's
completion call is accepted, that progress is reported, and that a refused
upload rejects with a message to show rather than failing silently.

**FullCalendar 5.11.3 -> 6.1.20, and it no longer has a stylesheet.**
FullCalendar 6 injects its own CSS from javascript, so
``vendors/fullcalendar/main.min.css`` does not exist any more: it is gone from
the readonly CSS bundle and from ``stylesheets.html``, and a project that
linked it by hand has to drop the link. The script is one global build with the
standard plugins already in it, ``index.global.min.js``, instead of
``main.min.js``. ``locales-all.js`` is no longer downloaded either -- it moved
to another package in 6, and no template had ever loaded it.

The widget API this library uses did not change: ``new FullCalendar.Calendar``,
``eventDidMount``, ``eventClick``, ``dateClick`` and the ``EventApi`` setters
all behave the same, and so do the three CSS overrides in ``calendar.html``
that target ``fc-daygrid-day-frame`` and friends -- which is exactly what a
major version is free to rename, so the calendar now has six browser tests
that pin the month grid, the injected styles, those overrides, the event
tooltip and the detail modal. It had none.

**TinyMCE 5.6.1 -> 8.8.2, under the GPL licence key.** From TinyMCE 7 the
editor is GPL-2.0-or-later, and from 8 a self-hosted build **loads read-only
unless a licence key is set**. The shared config now sends
``license_key: 'gpl'``, which is the open source option and matches what this
package ships under. A project that has bought a commercial key sets its own
by overriding the config.

Three things moved in the package itself:

* ``jquery.tinymce.min.js`` is not part of TinyMCE any more -- the jQuery
  integration became a separate project -- so ``$(el).tinymce(config)`` is now
  ``tinymce.init({target: el, ...})``, wrapped in a new
  ``gentelella_tinymce_init()``. Remove the second script tag if you load
  TinyMCE by hand.
* ``models/dom/model.min.js`` is new and **mandatory**: without it the editor
  does not start at all.
* The mobile theme and its ``*.mobile.min.css`` skins are gone.

**The plugin list went from 46 to 29.** ``paste``, ``print``, ``hr``,
``colorpicker``, ``contextmenu``, ``textcolor``, ``noneditable`` and
``tabfocus`` were absorbed into the core; ``bbcode``, ``legacyoutput``,
``spellchecker`` and ``textpattern`` were dropped; ``fullpage``,
``imagetools``, ``template`` and ``toc`` became premium. The toolbar was
trimmed to controls that exist: it had been asking for ``checklist``,
``casechange``, ``permanentpen``, ``formatpainter``, ``pageembed``,
``template``, ``a11ycheck``, ``showcomments`` and ``addcomment``, all premium
and all drawing nothing. ``fontselect``, ``fontsizeselect`` and
``formatselect`` are ``fontfamily``, ``fontsize`` and ``blocks``.
``directionality`` is now actually loaded, so the ``ltr``/``rtl`` buttons the
config had always asked for finally appear. ``paste_preprocess`` takes the
editor as its first argument instead of the plugin.

A project that passed its own ``plugins`` or ``toolbar`` has to check them
against the 29 that remain.

**``VoiceEditorTinymce`` needed one change**, and it is the kind that fails
silently: a toggle button's ``setDisabled`` became ``setEnabled`` in TinyMCE 6,
with the sense reversed. Three browser tests now drive that button with a fake
microphone, so the whole path -- the icon and button registration,
``setActive``, ``setEnabled``, ``setProgressState`` and the notification
manager -- is exercised rather than assumed.

**jQuery-Knob is gone; the dial of ``NumberKnobInput`` is an SVG of our own.**
The old plugin (2015, unmaintained) painted a ``<canvas>`` at a fixed pixel
size -- soft on any display past 1x -- and rebuilt its own keyboard handling
over an input it had emptied of meaning. ``gentelella/js/base/knob.js`` plus
``css/knob.css`` draw a stroked circle instead, and leave the
``<input type="number">`` in the middle of it as the value, the readout and the
focusable control: arrow keys, typing, ``min``/``max``/``step`` validation and
what a screen reader announces are the browser's own, and the svg is
``aria-hidden``, adding only what an input cannot do -- dragging round the dial
and the wheel.

It reads the same ``data-*`` options the old plugin did (``data-min``,
``data-max``, ``data-step``, ``data-width``, ``data-fgcolor``,
``data-bgcolor``, ``data-thickness``), so a form that configured a knob needs
no change; ``data-displayprevious``, ``data-cursor`` and the other
canvas-drawing options are ignored, since there is no canvas to draw. Size and
colour are also ``--gt-knob-size`` and ``--gt-knob-color``, settable in CSS.

Two long-standing bugs went with it. ``NumberKnobInput`` declared
``input_type = 'number'`` but its template never wrote the ``type`` attribute,
so the browser rendered a **text** field -- invisible while a canvas covered
it, and the reason the keyboard did nothing. And ``data-min``/``data-max``/
``data-step`` are now mirrored onto the native ``min``/``max``/``step``, so the
browser's own arrows and validation agree with the dial instead of stepping by
1 through a field declared ``data-step="0.1"``.

**iCheck and switchery are gone; checkboxes, radios and switches are CSS.**
Both libraries worked the same way: hide the real ``<input>`` and paint their
own DOM beside it. That is why every caller had to go through an imperative
API. ``gentelella/css/checks.css`` draws the native input instead
(``appearance: none`` plus a background image), so the control the user clicks
and the field the form submits are the same element again.

What that deletes, rather than ports:

* ``.iCheck('check' | 'uncheck' | 'update')`` -- 13 calls across
  ``permissionmanagement.js``, ``form.common.js``, ``obj_api_management.js``
  and ``custom.js``. Setting ``input.checked`` now repaints on its own.
* ``ifChecked`` / ``ifUnchecked`` / ``ifToggled`` -- 8 handlers, replaced by the
  native ``change`` event.
* The ``data-switchery`` bookkeeping in ``clear_action_form()``: a native form
  reset repaints the switches by itself.
* The hand-written ``<div class="icheckbox_flat-green">…<ins class="iCheck-helper">``
  in ``chunkedupload.html``, ``file.html``, ``pdfviewer.html``,
  ``crud_list.html`` and the javascript template in ``custom.widgets.js``.
* 17 vendored files (both libraries, five skin stylesheets and ten sprite PNGs),
  their ``loaddevstatic`` entries, their four ``pylpfile`` entries and the
  ``.switchery`` overrides in the four theme stylesheets. 36 KB of vendor code
  becomes 6 KB of ours.

**What changes for a project:** the widgets stamp ``gt-check`` (checkbox, radio,
multiple checkbox) or ``gt-switch`` (``YesNoInput``) instead of ``flat``, and
markup written by hand against ``icheckbox_flat-green`` has to become a plain
``<input class="gt-check">``. ``data-checkboxclass`` and ``data-radioclass``,
which chose an iCheck skin, no longer do anything; colour and size are
``--gt-check-color`` and ``--gt-check-size``, settable at runtime.

Three things work now that did not: the indeterminate state (the sprite had no
frame for it, so a partially selected "select all" box drew as empty), keyboard
focus (both libraries hid the input, so the focus ring went with it), and
``prefers-reduced-motion``.

**moment no longer ships all 137 languages to every page.** The bundle carried
``moment-with-locales.min.js``, 375 KB, so that one language could be used. It
now carries moment's core build (59 KB) and the page links the locale file for
the active language separately (~4 KB), through the new ``get_moment_locale``
tag in ``gtsettings``. ``loaddevstatic`` downloads the locales named by
``settings.LANGUAGES``, so a project that narrowed that setting downloads only
its own languages, and one that never set it keeps Django's full list and loses
nothing. English needs no file: it is built into the core build, and a language
moment has no translation for degrades to English rather than 404ing.

daterangepicker keeps moment -- it mutates moment objects in about twenty
places, so dayjs, which is immutable, is not a drop-in replacement for it.

**DataTables 1.12.1 -> 2.3.7, and 14 extensions dropped from the build.** The
bundle carried AutoFill, DateTime, FixedColumns, FixedHeader, KeyTable,
RowGroup, RowReorder, Scroller, SearchBuilder, SearchPanes, Select,
StateRestore, jszip and the colvis/html5/print buttons without a single
reference anywhere in the project -- row selection is hand rolled with
``.gtcheckable`` checkboxes, not the Select extension. What is left is
DataTables itself plus Buttons, ColReorder and Responsive: the vendored
directory goes from 668 KB to 194 KB.

What changes for a project that styles or scripts its own tables:

* **Every class DataTables generates was renamed**, ``dataTables_*`` ->
  ``dt-*``: ``dataTables_wrapper`` is ``dt-container``, ``dataTables_filter``
  is ``dt-search``, ``dataTables_paginate`` is ``dt-paging``,
  ``dataTables_length`` is ``dt-length``, ``dataTables_info`` is ``dt-info``,
  ``dataTables_processing`` is ``dt-processing``, ``dataTables_empty`` is
  ``dt-empty``. The four theme stylesheets were updated, and the
  ``paging_full_numbers``, ``DTTT_button`` (TableTools, gone since 2014),
  ``table.display`` and ``example_alt_pagination`` rules -- all DataTables 1.9
  markup that nothing in this project has emitted for years -- were deleted
  rather than renamed.
* **The ``dom`` string is now a ``layout`` object.**
  ``document.table_default_dom`` is ``document.table_default_layout``; a page
  that set its own ``dom`` (the notification list did) has to be ported.
* **``dt.context[0].nTable`` is gone**; use ``dt.table().node()``.
* The i18n files come from ``plug-ins/2.3.7/i18n/`` and their keys changed.
  ``DATATABLES_SUPPORT_LANGUAGES`` still points at them the same way.

The server side is untouched: ``formatDataTableParams`` already translated the
request into DRF's ``offset``/``limit``/``ordering``, and
``draw``/``recordsTotal``/``recordsFiltered`` mean the same thing in
DataTables 2. Seven browser tests now cover the wrapper, which had none.

**Chart.js 2.9.3 -> 4.5.1.** The whole chart configuration is built by
``djgentelella.chartjs`` and handed to ``new Chart()`` untouched, so the option
vocabulary in the serializers is now Chart.js 4's:

================================ ==========================================
Chart.js 2                       Chart.js 4
================================ ==========================================
``options.title``                ``options.plugins.title``
``options.legend``               ``options.plugins.legend``
``options.tooltips``             ``options.plugins.tooltip``
``scales.xAxes: [{...}]``        ``scales: {x: {...}}``
``scale.scaleLabel.labelString`` ``scale.title.text``
``scale.gridLines``              ``scale.grid``
``elements.rectangle``           ``elements.bar``
``dataset.steppedLine``          ``dataset.stepped``
``type: 'horizontalBar'``        ``type: 'bar'`` + ``indexAxis: 'y'``
================================ ==========================================

The ``get_<option>()`` hooks kept their names -- ``get_title``, ``get_legend``
and ``get_tooltips`` name a chart concept, not a configuration path -- and the
last five rows of that table are translated for a release: a ``get_scales``
still returning ``xAxes``/``yAxes``, an ``elements.rectangle`` block, a
``steppedLine`` dataset key and a ``get_type`` returning ``horizontalBar`` all
keep working. What does **not** survive is a **tooltip callback written for
Chart.js 2**: v3 replaced the ``(item, data)`` arguments with a single context
object, so every function registered in ``document.chartcallbacks`` has to be
rewritten. The two shipped with the library already are.

``options.plugins`` accepts anything, so third party plugins configured through
``get_plugins()`` are passed through untouched.

Two smaller consequences: ``vendors/chartjs/Chart.min.css`` is gone (Chart.js 3
dropped the stylesheet, everything is drawn on the canvas) and the script is
``vendors/chartjs/chart.umd.min.js``. A project that linked either path by hand
has to update it. ``gentelella/widgets/chart.html``, an orphan template no
include ever pointed at, was deleted; the live one is
``gentelella/widgets/chartjs.html``.

**Five javascript libraries are gone from the bundles.** None of them was doing
anything, and all five were downloaded and shipped on every page:

* **Parsley** (42 KB) -- no ``data-parsley-*`` attribute and no ``.parsley()``
  call has ever existed in the project.
* **patternfly-bootstrap-treeview** (27 KB) -- nothing calls ``.treeview()``;
  the ``TreeSelect*`` widgets are drawn by select2. It was also the only
  dependency fetched from a raw ``github.com`` URL.
* **bootstrap-progressbar** -- the plugin only reacts to ``data-transitiongoal``
  and no template sets it, so ``$('.progress .progress-bar').progressbar()``
  animated nothing. The call in ``custom.js`` went with it.
* **jQuery UI's stylesheet** -- downloaded, never linked. The one piece of
  jQuery UI still in the build is blueimp's private ``jquery.ui.widget`` shim,
  which comes with the file-upload plugin.
* **A second copy of interact.js** -- it was downloaded into both
  ``vendors/interact/`` and ``vendors/pdfjs/``, and both were loaded.

A project that referenced any of them directly has to vendor it itself.

**Javascript bundles are now joined with ``;\n``.** A minified vendor file that
ends in an expression without a trailing semicolon, followed by one that starts
with ``(``, used to concatenate into a single call expression: the bundle then
died at parse time and every library after that point disappeared silently.
Nothing to change downstream, but a custom ``pylpfile.py`` copied from this one
should pick up the ``sep=JS_SEP`` argument.

**Library upgrades.** jQuery 3.6.1 -> 3.7.1, inputmask 3.3.11 -> 5.0.10 (only
the jQuery build is shipped now; it already contains the whole library),
bootstrap-daterangepicker 3.0.5 -> 3.1.0, bootstrap-maxlength 1.10.0 -> 2.0.0
and ion-rangeslider 2.3.1 -> 2.3.2. The maxlength counter's
``warningClass`` moved from the Bootstrap 3 ``label label-success`` to
``badge text-bg-success``.

**Two dead asset links removed.** ``vendors/tagify/jQuery.tagify.min.js`` and
``vendors/pdfjs/pdf_viewer.min.css`` were requested by
``gentelella/statics/*.html`` but not downloaded by ``loaddevstatic``: a 404 on
every page in development and a hard failure under
``ManifestStaticFilesStorage``. The uncompressed branch also loaded
fileupload, tagify, TinyMCE and SweetAlert2 twice, and htmx not at all -- htmx
was only in the compressed bundle, and its vendor folder was misspelled
``vendors/htmlx/``. It is ``vendors/htmx/`` now.

**Country flags are no longer CSS classes.** ``<i class="fi fi-cr"></i>`` and
the ``use_flags`` define are gone, along with
``djgentelella.flags.vendors.min.css``. Replace them with the ``gtflags``
template tags::

    {% load gtflags %}
    {% flag 'cr' %}                  <!-- was <i class="fi fi-cr"></i> -->
    {% flag 'cr' square=True %}      <!-- was <i class="fi fi-cr fis"></i> -->

That stylesheet was 6.35 MB. It carried all 532 flag SVGs base64-inlined into
``background-image``, a 232x inflation of the 27 KB it started as, and a page
showing three flags downloaded every country in both aspect ratios before it
could render. The 532 SVGs were shipped a second time under
``static/vendors/flags/``, and ``loaddevstatic`` re-downloaded all of them from
a CDN on every run -- a network hiccup during a release quietly produced broken
flags.

Removing it also frees the ``.fi`` class, which flag-icons 6.6.6 and Friconix
both claim: with ``use_flags`` on, every Friconix ``<i class="fi fi-...">`` was
silently picking up flag-icons' ``background-size``, ``display`` and ``width``.

Projects that never used flags need to change nothing.

**django.contrib.sites is required.** The Site of menus and settings is a
foreign key to ``sites.Site``: add ``'django.contrib.sites'`` to
``INSTALLED_APPS``, set ``SITE_ID`` (Django's ``LoginView`` needs it) and run
``migrate``. Existing menus and settings stay global, so nothing else changes.
The key of a setting is now unique per Site (and globally among the global
rows); migration ``0022_site_scoping`` refuses to run while two global rows
share a key -- ``set_settings`` already failed on those keys -- and lists the
``pk`` and value of each, deleting nothing: keep one row per key and migrate
again. Without ``django.contrib.sites`` the system check ``djgentelella.E001``
says so.

**Hardening.** Four changes may need a look when upgrading:

- *The data-widget of a subclass is the one of its base.* The javascript
  initializes a widget by ``data-widget``, which used to be the class name, so
  a widget subclassed in a project lost its javascript. It is now
  ``js_widget_name(widget)``: the ``js_widget`` of the nearest class that sets
  it, or else the name of the nearest class of djgentelella. A project
  subclass with javascript of its own sets ``js_widget = 'MyWidget'``; one
  that already registered javascript under its class name
  (``document.gtwidgets.MyWidget``) keeps working without changes: the class
  name is rendered as ``data-widget-class`` and ``gt_find_initialize`` prefers
  it when something registered it.
- *FileChunkedUpload.format_value* returns plain JSON built with
  ``json.dumps`` (``<``, ``>`` and ``&`` escaped as ``\u00XX``) and no longer
  marked safe; the template escapes it into the attribute. Code that put
  ``widget.value`` in a template with ``|safe`` gets the same text.
- *A JSON flow names only allowed callables.* ``publish_definition`` refuses a
  ``FlowDefinition`` whose conditions, ``call`` actions or transition forms
  name a dotted path that is not registered (``register_callable``,
  ``register_condition``) nor listed in ``GT_FLOWS_ALLOWED_CALLABLES``
  (empty by default); a stored one still loads, and the callable is refused
  and logged when it runs. Flow classes in Python are not affected.
- *0022_site_scoping fails on duplicated global settings* instead of deleting
  them (above).

**The tasks of a deleted object are kept, cancelled.** Deleting the object of
a flow instance used to delete its tasks with the instance; now the open ones
are cancelled first and all of them stay, as tasks of no flow (``instance``
empty), with their history. ``{% gt_datasource_export %}`` without
``formats`` offers the formats of the request (``available_formats``) instead
of always ``csv,xlsx,json,pdf``, and ``gtCreateDataSourceTable`` without
``formats`` the ones the source endpoint lists.

New features
""""""""""""""""""

**Country flags from a committed sprite, served on demand.** All 266 flags now
ship as one gzipped SVG sprite,
``static/gentelella/flags/flags.4x3.svg.gz`` (~650 KB), built by the new
``manage.py buildflagsprite`` command and committed to the repository -- nothing
is downloaded at build or install time.

* ``{% flag 'cr' %}`` (``djgentelella.templatetags.gtflags``) renders an
  ``<svg><use>`` into the sprite: one request serves every flag on the page,
  cached across pages. ``square=True``, ``css_class`` and ``title`` are
  supported, and an unknown code renders nothing.
* ``/flags/<code>.svg`` returns a single flag, with optional ``size``, ``shape``
  (``circle`` or ``rounded``) and ``title`` applied at request time.
  ``djgentelella.flags.flag_url()`` builds the URL from Python.
* ``/flags/sprite.svg`` serves the sprite, handed over still gzipped.
* Flags in a select2 autocomplete need no new JavaScript: a
  ``BaseSelectImg2View`` whose ``get_url()`` returns ``flag_url(obj.code)``
  makes ``AutocompleteSelectImage`` draw a flag per option. The demo shows it at
  ``/imageselect/create/``, where the same widget sits beside one fed by
  uploaded ``FileField`` images -- the only difference between them is what
  ``get_url()`` returns -- and on the person form, where it also has to survive
  being cloned into a formset row and a modal.

``cefta`` was missing from the download list, so ``.fi-cefta`` had been defined
in the CSS and 404ing since 6.6.6 landed; the sprite has it.

The wheel is 2.4 MB smaller to download (11.8 MB -> 9.5 MB) and about
11.9 MB smaller once installed, where the base64 and the SVGs were no
longer compressed.

See ``docs/source/icons.rst``.

Fixes
""""""""""""""""""

**Seven test modules never ran.** ``djgentelella/tests`` modules are found
only through the star imports of its ``__init__.py``, and BreadcrumbNav,
FilteredSelectMultiple, FirmadorToken, Flows, History, PositionsGrid and
Select2Autocomplete were missing from it -- CI passed without them. They run
now, and History's exposed ``add_log`` storing an integer ``object_id`` on
``LogEntry``, fixed.

``loaddevstatic`` dropped the last chunk of its download queue whenever the
number of files was an exact multiple of the thread count, so a library could
silently never appear under ``vendors/``.

``MapPointInput`` leaked event handlers. The ``based_fields`` listeners are
bound on *other* fields, and ``destroy()`` only unbound the widget's own input,
so a re-rendered widget -- a formset row, a reopened modal -- left a live
handler on a sibling field closing over a map that no longer existed. A
malformed ``data-based-fields`` also threw out of ``JSON.parse`` and killed the
rest of the widget initialisation, leaving an input with no map; it now falls
back to no geocoding and reports the problem on the console.

``TrashViewSet.restore`` printed the exception to stdout instead of logging it,
so the reason a restore failed never reached the application log.

**Maps rendered as empty squares on a default Django project.** Django sets
``SECURE_REFERRER_POLICY = 'same-origin'``, so the browser sends no ``Referer``
on the cross-origin requests every tile is, and OpenStreetMap's tile policy
answers 403 without one. The demo now sets
``SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'`` and
``docs/source/widgets/maps.rst`` says why any project using these widgets has
to do the same. The demo also listed ``SecurityMiddleware`` twice.

**Material Design Icons, opt-in.** 7448 icons as a webfont, shipped inside the
package -- nothing is fetched from a CDN at runtime -- and loaded only where a
template asks for it::

    {% load gtsettings %}
    {% block pre_head %}{% define_true "use_mdi" %}{% endblock %}

    <i class="mdi mdi-home"></i>

Only the woff2 is downloaded. Upstream's ``@font-face`` also lists eot, woff and
ttf -- the same glyphs in three encodings no supported browser would pick -- so
``loaddevstatic`` rewrites the rule to the woff2 alone instead of shipping
2.3 MB of fonts. It is deliberately not part of any pylp bundle: ``urlreplace``
would base64 the font into ``djgentelella.vendors.min.css``, and the point of a
webfont is that the browser fetches one 403 KB file and caches it.

**PDF viewer widget.** ``PDFViewerWidget`` displays a PDF from a ``FileField``
with page navigation and zoom, rendering client-side through pdf.js;
``PDFFileField`` validates the extension, the content type and the magic bytes,
and uploads go through a PDF-specific chunked endpoint
(``upload_pdf_view`` / ``upload_pdf_done``) rather than the generic one. Demo at
``/pdfviewer/``.

``gentelella/css/pdfviewer_widget.css`` is linked from the base template rather
than left for each project to remember, on the same reasoning as ``maps.css``:
without it the canvas has no size and the controls no layout.

**A reference page per icon set**, under an **Icons** menu in the demo sidebar:
``/icons/fontawesome`` (786), ``/icons/friconix`` (1559), ``/icons/mdi`` (7448)
and ``/icons/flags`` (266). Each is searchable, and each reads its set from what
the browser already loaded -- friconix's ``paths`` global, the CSS rules Font
Awesome and MDI declare, the ``<symbol>`` elements of the flags sprite -- so no
list can drift from the version ``loaddevstatic`` downloaded. The flags page
also previews the ``square``, ``circle`` and ``rounded`` shapes, and the
friconix page lets you try a mask against every icon at once.

**The sidebar menu escapes what it reads from the database.** The titles,
links and icons of ``sidebar_menu`` and ``footer_sidebar_menu`` were put in the
page as they were, so a ``MenuItem.title`` of ``<img src=x onerror=...>`` ran
in every page. They are escaped now, as ``top_menu`` already did; a title with
HTML in it shows the HTML as text.

**A GTForm no longer changes the template of every other form.** Its
``render_type`` was stored on ``self.renderer`` -- the renderer every form of
the process shares -- so after one ``as_grid`` GTForm (the modals of a design
table, for instance) a plain Django form rendered as an empty grid. The
template is now chosen per instance (``GTForm.template_name``).

Dependencies
""""""""""""""""""

Eleven frontend libraries moved up, all within a compatible range and verified
against the browser suite (57 Selenium tests):

* ``select2`` 4.1.0-**rc.0** -> 4.1.0 -- the bundle had been shipping a release
  candidate.
* ``moment.js`` 2.13.0 -> 2.30.1. The pin was from 2016 and sat below every
  security fix in the 2.29.x line.
* ``bootstrap`` 5.2.0 -> 5.3.8 and ``@popperjs/core`` 2.11.5 -> 2.11.8.
* ``parsley.js`` 2.3.13 -> 2.9.2, ``@yaireo/tagify`` 4.33.2 -> 4.38.0,
  ``htmx.org`` 2.0.4 -> 2.0.10, ``squirrelly`` 9.0.0 -> 9.1.1,
  ``spark-md5`` 3.0.0 -> 3.0.2, ``iCheck`` 1.0.2 -> 1.0.3,
  ``interact.js`` 1.10.27 -> 1.10.28.

``interact.js`` was also being downloaded twice, once from an **unpinned**
``cdn.jsdelivr.net/npm/interactjs/`` that resolved to whatever was current that
day. Both copies are now pinned to 1.10.28.

``pdf.js`` 4.6.82 -> 6.2.108. ``globalThis.pdfjsLib`` is still exposed by the
``.mjs`` build and ``getViewport``/``render`` are unchanged, but **6.x dropped
``getDocument``'s bare-string shorthand**: a relative string, an absolute string
and even a ``URL`` object are all rejected with "expected either ``data``,
``range``, or ``url`` parameter", and the rejection is asynchronous, so the
canvas simply stays blank at its default 300x150. Both call sites now pass
``{url: ...}``.
``pdf_viewer.min.css`` is gone from the bundle: 6.x no longer publishes it, and
it styled only the text, annotation and XFA layers, none of which anything here
renders. Its 15 ``images/`` SVGs went with it -- they existed solely to feed its
``url()``\ s.

Two more moved a major version each, both verified in a browser rather than by
version number alone: ``autosize`` 3.0.15 -> 6.0.1 (the global still takes a
textarea and still grows it) and ``sweetalert2`` 10.10.0 -> 11.26.25
(``Swal.fire``, ``Swal.mixin``, ``stopTimer``/``resumeTimer`` and the
``didOpen`` hook all survive; none of the options v11 dropped were in use).

``patternfly-bootstrap-treeview`` was downloaded from the **master branch** and
is now pinned to ``v2.1.10``, which is byte-identical to what master serves
today -- a pin that swaps nothing.

**Checksums for the sources that cannot be pinned.** Knightlab's StoryMap and
Timeline are fetched from ``latest``, and friconix from a URL with no version at
all, so two builds of the same commit could differ with nothing to show for it.
``loaddevstatic`` now records a SHA-256 for each and reports, in a summary block
at the end of the run, any that changed since they were last vetted.

Knightlab's numbered releases are deliberately **not** used: ``latest`` is the
current webpack build of StoryMapJS (260 KB, ``KLStoryMap`` namespace) while its
newest tag, 0.7.1, is unminified 2019 code on the old ``VCO`` architecture at
twice the size. Pinning to it would be a four-year downgrade, not a pin --
and it embeds a different Leaflet, which ``maplib.js`` asserts against at
runtime.

Removed from ``loaddevstatic``:

* **summernote 0.8.18** -- downloaded and packaged, but in no bundle and no
  template. The only caller was ``uploadFile()`` in
  ``gentelella/js/base/wysiwyg.js``, which nothing called either and which would
  have thrown ``$(...).summernote is not a function`` if it had. Both are gone;
  the wysiwyg widgets use TinyMCE's own upload endpoints.
* **Bootstrap 3 glyphicons** (216 KB, five font files from the retired MaxCDN)
  -- no bundled stylesheet has ever referenced one. ``vendors/fonts/`` now holds
  only the Font Awesome faces that ``font-awesome.min.css`` actually reaches.
* A ``bootstrap-datetimepicker`` sourcemap that has always 404ed, printing a
  ``FAILED`` line on every run.

**pdf.js parsed every document on the main thread.** The worker was loaded as a
second ``<script type="module">``, which downloads a megabyte into the page and
leaves ``GlobalWorkerOptions.workerSrc`` empty -- so pdf.js silently fell back
to its fake worker and blocked the UI while parsing. It is now handed to pdf.js
as a URL, and the parsing really does happen off-thread.

Fixes
""""""""""""""""""

**Friconix icons never appeared on anything built after page load.** Friconix
hooks ``document.onreadystatechange``, scans once and has no
``MutationObserver``, so an ``<i class="fi-...">`` inside a formset row, a
reopened modal or a DataTables redraw stayed an empty element. djgentelella now
rescans from ``gt_find_initialize()`` -- the hook every widget already
re-initialises through -- and exposes ``gt_friconix_refresh()`` for markup
injected by hand. Removing the flag-icons stylesheet helps here too: it defined
``.fi``, the same class friconix marks its icons with.

The demo gained a searchable grid of all 1559 icons at ``/friconix``, and
``docs/source/icons.rst`` now documents the six-letter mask grammar instead of
pointing at an external site.

Tooling
""""""""""""""""""

``make test-selenium`` now runs inside its own X server (``xvfb-run -a``), so
the browser the tests drive cannot steal focus from the developer's session.
``SELENIUM_HEADLESS=0`` draws a real Chrome inside it -- useful for the
Leaflet, canvas and TinyMCE widgets -- and ``make test-selenium-run`` keeps the
old behaviour of running on the caller's display.

``make coverage`` and ``make coverage-all`` measure the package, the second one
combining the unit and the browser suites into a single report. Configuration
lives in ``pyproject.toml``; ``coverage`` is not a declared dependency, install
it yourself. The unused ``[tool.black]`` section was dropped -- the formatter
this project actually uses is ``ruff format``.

Review fixes
""""""""""""""""""

**A ``Wait`` needs ``next``.** Its signal and its timeout both move the token
there; without it ``flow.signal()`` raised ``KeyError`` (a 500) and the timer
retried on every ``process_flow_timers`` forever. ``Wait(...)`` without
``next`` is now ``ImproperlyConfigured``, and so is building or publishing a
JSON flow whose ``wait`` lacks it -- check stored definitions before upgrading.

**Long chains of automatic activities.** The engine used to nest a few Python
frames per move, so a chain of some 200 automatic activities hit
``RecursionError`` long before ``Run.MAX_STEPS`` (500). Moves now run from a
depth-first queue in a loop: any chain under the limit completes, and a loop
of automatic activities ends with the ``ImproperlyConfigured`` that names it.
The ``on_enter`` actions of the branches of a ``Parallel`` all run when it
forks, before the first branch does its work.

**Subflows nest at most ``GT_FLOWS_MAX_SUBFLOW_DEPTH`` deep** (10 by default).
Flows that start each other on new objects used to recurse without limit
inside one transaction; the ``Subflow`` past the limit is now left in error.

**``action_from_json`` guards a ``call`` by itself.** The ``function`` of a
``call`` built from JSON goes through the allowlist of JSON flows
(``GT_FLOWS_ALLOWED_CALLABLES``, ``register_callable``) when it runs, even if
the caller does not wrap it with ``guard_action``. ``action_from_json`` takes
an optional ``where`` for the log, and ``guard_action`` on an action already
guarded only updates that place. ``CallFunction('pkg.fn')`` written in Python
is unchanged.

**One autodiscovery, safe between threads.** ``djgentelella.utils.
autodiscover_once(module_name)`` imports ``<app>.<module_name>`` of every app
once, under a lock, and counts it as done only after the imports worked. The
authorizations (``gtauth``), the LOVs (``gtlovs``) and the data sources
(``gtdatasources``) use it; the authorization registry used to mark itself
discovered before importing, so a request on another thread at startup could
find it empty and deny. The registry of design components loads under a lock
too.

**LOVs of ``values_list()`` validate the value they offer.** ``LOV.find``
(and so ``LOVChoiceField``) filtered every queryset by ``pk``, while the
options of a ``values_list('code', 'name')`` carry ``code``: a valid option was
rejected, or a row whose pk matched by chance was accepted. Querysets of models
are still looked up by pk; the others by their first column. The options of a
``values()`` queryset are now its first two columns instead of the whole dict.

**Aggregates and pivots have a cap: ``GT_DATASOURCE_MAX_GROUPS``** (1000 by
default). More groups, or more pivot rows or columns, than that is a
``ValidationError`` -- a 400 from the data source API -- instead of loading
every group in memory; results under the cap are unchanged. ``aggregate()``
takes ``order_by_value`` and ``limit``, and the charts of designs use them to
read only their top groups, ordered in the database. The pivot composed in
Python keeps its row and column values in dicts instead of lists.

**The HTML of designs keeps only Bootstrap's ``data-*`` attributes.** The
sanitizer kept every ``data-*``, so a publisher without ``publish_js`` could
write ``data-widget``, ``data-url`` or ``data-gt-dynamic`` and have a widget of
the page initialised with values of their choosing. Now only ``aria-*`` and
the ``data-*`` Bootstrap reads to toggle, collapse, dismiss and slide are kept
(``djgentelella.designs.sanitize.DATA_ATTRIBUTES``); ``data-bs-html``,
``data-bs-sanitize`` and ``data-bs-template`` are dropped too. Designs whose
``html`` nodes rely on other ``data-*`` lose them.

**Cycles of dynamic actions stop.** The ``MAX_DEPTH`` guard of
``dynamic_actions.js`` counted only the synchronous part of a change, and the
actions run in promises, so two rules feeding each other values that never
converge (or a ``set_value(server=...)`` that answers a new value every time)
looped forever. The depth now travels with the change that a ``set_value``,
a ``refresh`` or a ``call``'s ``setValue`` fires, and a cascade stops after ten
changes.

0.6.0
-------

Breaking changes
""""""""""""""""""

**Django 5.2 (LTS) is now the minimum**, along with Django REST Framework
3.15.2. Python 3.11 remains the floor.

**``InlineAjaxCRUD`` was removed**, together with the ``inlines`` attribute of
``CRUDView``, the ``crud_inline_url`` template tag and the
``templates/cruds/ajax/`` template set. It rendered the children of an object as
server side HTML fragments swapped in with djangoajax, a pattern nothing else in
the project used. Replace it with
:class:`~djgentelella.objectmanagement.BaseInlineObjectManagement`, which manages
the same relation through the regular ``ObjectCRUD`` javascript over a queryset
scoped to one parent::

    class NoteManagement(BaseInlineObjectManagement):
        queryset = Note.objects.all()
        parent_model = Project
        parent_field = 'project'

    router.register(r'project/(?P<parent_pk>[^/.]+)/note',
                    NoteManagement, 'api-project-note')

See ``docs/source/object_management.rst`` for the full example.

**django-markitup is gone from the blog.** ``Entry.resume`` and
``Entry.content`` are plain ``TextField``\ s edited with ``EditorTinymce``.
Remove ``'markitup'`` from ``INSTALLED_APPS`` and drop the ``MARKITUP_FILTER``,
``MARKITUP_SET`` and ``markitup_preview`` URL entries. Existing databases are
migrated by ``blog.0002``, which moves the HTML held in the ``_resume_rendered``
and ``_content_rendered`` columns into ``resume``/``content`` and then drops
those columns; without it every insert fails on them (they are NOT NULL) and the
markdown source would be served verbatim. The migration cannot be reversed, and
its raw ``DROP COLUMN`` needs SQLite 3.35 or newer — **back up the blog tables
before upgrading**.

.. warning::

   Entry bodies are now stored and served as HTML written in TinyMCE, and
   gentelella does not sanitize them. Anyone holding ``blog.add_entry`` or
   ``blog.change_entry`` can therefore place arbitrary HTML and JavaScript on
   the public entry list and detail pages, which carry no permission check.
   Grant those permissions to trusted authors only, or wrap the fields in your
   own sanitizer if the blog is open to untrusted writers.

**The tree select fields are form fields, not widgets.**
``GentelellaTreeNodeChoiceField`` and ``GentelellaTreeNodeMultipleChoiceField``
now derive from ``ModelChoiceField``/``ModelMultipleChoiceField`` instead of
``forms.Select``, so they are declared as the field, not passed as ``widget=``::

    # before (never actually worked)
    node = forms.ModelChoiceField(queryset=..., widget=GentelellaTreeNodeChoiceField(...))
    # now
    node = GentelellaTreeNodeChoiceField(queryset=...)

In practice nothing breaks: the previous code called
``forms.Select.__init__(queryset)`` and raised ``AttributeError`` on
construction, and it read MPTT internals that have not been a dependency since
2022.

**The transcription endpoint answers 403 json instead of redirecting.**
``voice_transcribe`` enforces authentication itself and must not be wrapped in
``login_required``: its caller is the widget's ``fetch``, which would follow the
302 and fail parsing the login page as json.

**Dependencies dropped**: ``djangoajax``, ``django-markitup`` and ``markdown``
are no longer installed, and the dead ``static/django_ajax/`` files were
removed. The ``firmador`` extra now uses lower bounds instead of ``==`` pins,
which made it unresolvable next to any project needing a newer ``requests``,
``channels`` or ``django-cors-headers``.

New features
""""""""""""""

**Voice dictation widgets** (``VoiceDictation``, ``VoiceEditorTinymce``) with
progressive Web Audio + VAD capture, and a transcription endpoint
(``voice_transcribe``) with two interchangeable backends selected
by ``GENTELELLA_ASR_BACKEND``::

    pip install "djgentelella[asr]"          # local, in-process Parakeet-v3
    pip install "djgentelella[asr-remote]"   # forward to an external ASR API

Neither extra is needed to install or import djgentelella; without the matching
one the endpoint answers ``501`` naming it. See
``docs/source/widgets/voice.rst``.

**``BaseInlineObjectManagement``** for REST-driven CRUD over the children of a
parent object, scoped by the queryset so a child of another parent answers 404.

**``celery`` extra** for the ``async_notification`` queue backend. Without it
notifications are dispatched in-process by ``SyncBackend``, with nothing to
configure.

The project is now classified **Production/Stable** rather than Beta.

Fixes
"""""""

- The tree select fields are rebuilt on ``django-tree-queries`` (see the
  breaking change above). Options are now indented at any depth: the themes only
  defined ``.l2`` and ``.l3``, so levels 0, 1 and 4+ rendered flush left.
  ``TreeSelectMultiple`` was never registered in ``widgets.js`` and did not
  indent at all. ``disableN`` accepts any depth and honours its value, so
  ``disable1=False`` no longer disables level 1. Replacing ``field.queryset``
  after construction — the usual way to scope a field inside a form's
  ``__init__`` — keeps the tree depths; it used to silently flatten the whole
  tree.
- ``BaseObjectManagement.list`` counted ``recordsTotal`` from the class level
  ``queryset`` instead of ``get_queryset()``, so any subclass narrowing the
  queryset reported the unfiltered total.
- ``decore_form_instance`` carried a branch comparing ``type(field)`` against a
  string, dead since the MPTT removal in 2022; removed.
- The ASR backend selection treats an empty setting as unset, since both it and
  the remote URL are usually wired to ``os.getenv``.
- ``MANIFEST.in`` grafts the whole package, so a module cannot be released
  without its templates. ``async_notification``'s 23 templates and 3 static
  files were absent from the build; ``make check-dist`` now fails the release
  when any tree is missing.
- ``make release`` no longer passes ``twine upload -s``: PyPI stopped accepting
  GPG signatures in 2023. ``make sdist`` runs ``makemigrations --check``
  instead of ``makemigrations``, so a release fails on model drift rather than
  shipping a migration nobody reviewed.
