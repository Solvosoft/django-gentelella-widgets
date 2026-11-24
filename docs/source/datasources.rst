Data sources
============

A **data source** is a Python object that names a set of rows, the columns it
exposes and who may read them. It is what an Oracle APEX region gets from a
``SELECT``, written with the ORM instead of SQL. On top of a data source
djgentelella runs a query engine driven by a JSON document (filters, search,
ordering, grouping, aggregates, pivot and facets), exports the result as CSV,
XLSX, JSON or PDF, and serves both as REST endpoints that a table, a facets
panel and an export menu consume.

Data sources live in ``djgentelella.datasources``, an app with no models:

.. code:: python

    INSTALLED_APPS = [
        ...
        'djgentelella',
        'rest_framework',
        'djgentelella.datasources',   # app label: gtdatasources
    ]

The XLSX export needs ``openpyxl`` and the PDF export ``xhtml2pdf`` (0.2.28 or
later); install them with the extras ``pip install "djgentelella[export,pdf]"``.
CSV and JSON need nothing.

Declaring a data source
-----------------------

Write them in ``<app>/gtdatasources.py``. The module is imported from
``AppConfig.ready()``, like ``gtflows.py``, so the sources exist in management
commands and Celery workers too.

.. code:: python

    from djgentelella.datasources.base import (
        Column, FunctionDataSource, ModelDataSource, register_datasource)

    from . import models

    # A model, all of its fields.
    register_datasource(ModelDataSource(models.Order))

    # A subclass, registered with no arguments.
    @register_datasource
    class CustomerSource(ModelDataSource):
        model = models.Customer
        name = 'sales.customers'
        fields = ['id', 'name', 'country', 'country__region', 'created']
        site_field = 'site'

    # Rows computed in Python: any function that returns a queryset.
    def overdue(request):
        return models.Invoice.objects.filter(due__lt=date.today(), paid=False)

    register_datasource(FunctionDataSource(overdue, [
        Column('number', 'Number', 'string'),
        Column('customer', 'Customer', 'fk'),
        Column('total', 'Total', 'decimal'),
        Column('due', 'Due', 'date'),
    ], name='sales.overdue', perms=['sales.view_invoice']))

``get_datasource('sales.customers')`` returns a registered source and
``register_datasource`` replaces a name that already exists.

ModelDataSource
~~~~~~~~~~~~~~~

``ModelDataSource(model, *, name=None, label=None, fields=None, exclude=(),
queryset=None, perms=None, site_field=None, columns=None)``; every argument can
be a class attribute instead.

``name``
    Registry key; ``<app_label>.<model_name>`` by default.
``fields`` / ``exclude``
    The columns. By default every concrete field and forward many-to-many.
    A field can be an ORM path across relations, ``'country__name'``.
``queryset``
    Base queryset, ``model._default_manager.all()`` by default.
``perms``
    Permissions the user needs, all of them. ``None`` (the default) means the
    model's ``view`` permission; ``[]`` means nobody is checked, anonymous
    users included.
``site_field``
    The field holding a ``django.contrib.sites`` Site. Rows are limited to the
    current Site and to the global ones (field empty), with the same rule the
    menus and settings follow: the current Site is
    ``djgentelella.sites.get_current_site(request)`` (``request.site``, else
    the Site of the host, never ``SITE_ID``; see :doc:`sites`).
``columns``
    Extra or replacement ``Column`` objects, by name.

The column kind comes from the model field:

==============================================  ============
Field                                           Kind
==============================================  ============
``CharField``, ``EmailField``, ``UUIDField``…   ``string``
``TextField``                                   ``text``
``IntegerField`` and the rest of its family     ``integer``
``DecimalField``, ``FloatField``                ``decimal``
``BooleanField``                                ``boolean``
``DateField``                                   ``date``
``DateTimeField``                               ``datetime``
``ForeignKey``, ``OneToOneField``               ``fk``
``ManyToManyField``                             ``m2m``
any field with ``choices``                      ``choices``
``JSONField``                                   ``json``
==============================================  ============

Numeric columns are ``aggregatable`` unless they are the primary key;
many-to-many columns are not ``sortable``; file fields are not
``filterable``.

Writing one by hand
~~~~~~~~~~~~~~~~~~~

Anything that answers three questions is a data source:

.. code:: python

    class DataSource:
        name: str
        label: str
        def columns(self, request) -> list[Column]: ...
        def get_queryset(self, request) -> QuerySet: ...  # already filtered
        def has_permission(self, request) -> bool: ...    # checks self.perms

``perms`` on ``DataSource`` and ``FunctionDataSource`` is ``None`` by
default, which lets in **any authenticated user** and nobody else. A list
asks for all of its permissions (and a logged-in user); ``perms=[]`` opens
the source to anyone, anonymous users included, so a public source is always
written as such. ``ModelDataSource`` turns ``None`` into the model's ``view``
permission instead. ``FunctionDataSource`` checks the permission before it
calls its function, so ``fn`` never runs for a user without it: its
``get_queryset`` then returns ``model._default_manager.none()`` if the source
was given ``model=``, and raises ``PermissionDenied`` otherwise. Remember that ``djgentelella.urls`` serves every
registered source (see `REST API`_).

``search_mode`` (``'auto'``, ``'fulltext'`` or ``'icontains'``) and
``search_config`` (the PostgreSQL text search configuration, such as
``'spanish'``) tune the search.

Query parameters
----------------

Everything below takes the same JSON document, which is also what a saved
report stores. Every key is optional:

.. code:: json

    {
      "search": "text",
      "filters": [{"column": "status", "op": "in", "value": ["A", "B"]}],
      "ordering": ["-created"],
      "columns": ["id", "customer", "total"],
      "group_by": ["status"],
      "aggregates": [{"column": "total", "fn": "sum"}],
      "pivot": {"rows": "customer", "columns": "status",
                "value": {"column": "total", "fn": "sum"}},
      "highlights": [{"filter": {"column": "total", "op": "gt", "value": 1000},
                      "css": "table-danger"}]
    }

Every column, operator and value is checked against ``columns()`` before it
reaches the ORM. An unknown column, an operator the column's kind does not
allow or a value that cannot be read as that kind raise ``ValidationError``
(a 400 from the API), so a document can never reach a field the source does
not expose.

A ``decimal`` value has to be a finite number: ``NaN`` and the infinities
are refused, and so is a number with more whole digits than its column holds
(``max_digits - decimal_places`` of a model ``DecimalField``, which
``ModelDataSource`` copies into ``Column.max_digits`` and
``Column.decimal_places``) or past ``10**±1000`` on any decimal column. They
are a ``ValidationError`` too, not a database error.

Validating a document
~~~~~~~~~~~~~~~~~~~~~

To check a document before storing it -- a saved report, a subscription --
without running it, use ``validate_params``:

.. code:: python

    from djgentelella.datasources.query import validate_params

    clean, errors = validate_params(source, request, params)
    if errors:
        for error in errors:      # Error(path, message), str() 'path: message'
            print(error)          # $.aggregates[0]: sum is not allowed on nombre.
    else:
        save(clean)               # normalized: every key, as parse_params()

It reports **every** problem with the JSON path of its entry: the filters
(``$.filters[i]``), the ordering, the ``columns`` (unknown or listed twice),
the ``group_by`` entries, the aggregates, the pivot (``$.pivot.rows``...) and
the highlights (a ``filter`` object and CSS class names in ``css``). When
that passes and the user may read the source, the queryset is built -- not
run -- so the ORM checks the values too. ``strict=True`` also refuses unknown
keys, at the top level and inside the entries. ``clean`` is ``None`` when
there are errors.

The checks of one entry are public as well: ``group_expr(colmap, item,
index=0)`` and ``aggregate_expr(colmap, spec)`` take ``source.column_map()``
and raise ``ValidationError`` (they were ``_group_expr`` and
``_aggregate_expr``, names that still work).

Filters
~~~~~~~

Several filters are combined with AND.

.. list-table::
   :header-rows: 1
   :widths: 15 50 35

   * - Operator
     - Value
     - Kinds
   * - ``eq``
     - a value
     - all
   * - ``ne``
     - a value; rows where the column is empty match too
     - all but ``m2m``
   * - ``lt``, ``lte``, ``gt``, ``gte``
     - a value
     - numeric, dates
   * - ``in``
     - a list
     - all but ``boolean`` and ``json``
   * - ``contains`` (case-sensitive), ``icontains``, ``startswith``
     - text
     - ``string``, ``text``
   * - ``isnull``
     - ``true`` or ``false``
     - all
   * - ``between``
     - ``[low, high]``, inclusive; ``null`` leaves that side open
     - numeric, dates
   * - ``date_period``
     - ``{"period": "month", "date": "2026-10-15"}`` or
       ``{"period": "month", "offset": -1}``
     - ``date``, ``datetime``

``fk`` and ``m2m`` values are primary keys, ``choices`` values are the stored
keys. ``date_period`` selects the period (``year``, ``quarter``, ``month``,
``week`` or ``day``) that holds ``date``, or the one ``offset`` periods away
from today: ``{"period": "month", "offset": -1}`` is last month. A filter on a
many-to-many goes through a subquery, so a row that matches two related
objects is still one row.

Search
~~~~~~

``search`` looks in the ``string`` and ``text`` columns. On PostgreSQL, with
``django.contrib.postgres`` installed, it is full-text search with
``SearchVector`` and ``SearchQuery``: plain words are prefixes (``"gam"``
finds *Gamma*, as in a search box being typed into) and quotes, ``or`` and a
leading ``-`` follow the web search syntax. Anywhere else, SQLite included, it
is ``icontains`` on each column.

Grouping, aggregates and pivot
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Functions: ``count``, ``count_distinct``, ``sum``, ``avg``, ``min`` and
``max``. ``sum`` and ``avg`` need an aggregatable column, ``min`` and ``max``
an aggregatable or date one; ``count`` takes no column to count rows.

.. code:: python

    from djgentelella.datasources import query

    query.aggregate(source, request, {
        'group_by': ['status', {'column': 'created', 'period': 'month'}],
        'aggregates': [{'column': 'total', 'fn': 'sum'}, {'fn': 'count'}]})
    # [{'status': 'A', 'status__display': 'Open', 'created': date(2026, 1, 1),
    #   'total__sum': Decimal('120.00'), 'count': 3}, ...]

A ``group_by`` entry is a column or ``{"column", "period"}`` for dates. Without
``group_by`` the result is one row of totals. The groups come in the order of
their values; ``order_by_value=True`` puts the largest first aggregate first
(an empty one counts as 0) and ``limit=N`` keeps the first ``N`` -- both in
the database, which is how the charts of designs read their top groups.

**At most ``GT_DATASOURCE_MAX_GROUPS`` groups** (1000 by default): without a
``limit``, more groups than that is a ``ValidationError`` (a 400 from the
API) instead of a result, since grouping by a column with a value per row
would load the whole table. The same cap applies to the rows and, separately,
to the columns of a pivot.

``query.pivot`` crosses ``rows`` by ``columns`` and returns
``{"rows", "columns", "data", "row_labels", "column_labels"}``, where
``data[i][j]`` is the value of ``rows[i]`` and ``columns[j]``. When the pivot
columns are known in advance (a ``choices`` or ``boolean`` column) the table
is a single ``values().annotate()`` query with one ``Case/When`` aggregate per
column; otherwise the column values come from the data and the table is
composed in Python.

Facets
~~~~~~

``query.facets(source, request, params, ['status', 'total', 'created'])``
counts the rows per value of each column. As in APEX's Faceted Search, the
count of a facet applies **every filter except its own**, plus the search:
choosing a status narrows the other facets and keeps the other statuses
visible.

Each entry is ``{"value", "label", "count", "op"}``; ``op`` and ``value`` are
the filter that selects it. Value columns list their values (``in``, or
``eq`` for booleans, ``isnull`` for the empty one), numeric columns five
ranges (``between``) and date columns periods (``date_period``), by year,
month or day depending on how far apart the data is.

Highlights
~~~~~~~~~~

``highlights`` paints the rows that match a filter: the ``rows`` endpoint sets
``DT_RowClass`` (DataTables puts it on the ``<tr>``), XLSX turns it into
conditional formatting and PDF into a row background. The Bootstrap
``table-*`` classes have a color in both; any other class gets yellow, and
``#rrggbb`` (six hexadecimal digits) is used as is; anything else that starts
with ``#`` is ignored.

REST API
--------

``djgentelella.urls`` serves every registered source under
``gtapis/datasources/<name>/``:

.. list-table::
   :header-rows: 1
   :widths: 25 50 25

   * - URL
     - Answer
     - URL name
   * - ``<name>/``
     - ``{"name", "label", "columns", "formats"}``
     - ``gtdatasource``
   * - ``<name>/rows``
     - a page in the DataTables format: ``data``, ``recordsTotal``,
       ``recordsFiltered``, ``draw``
     - ``gtdatasource-rows``
   * - ``<name>/aggregate``
     - ``query.aggregate``
     - ``gtdatasource-aggregate``
   * - ``<name>/pivot``
     - ``query.pivot``
     - ``gtdatasource-pivot``
   * - ``<name>/facets``
     - ``query.facets`` of ``?columns=a,b``
     - ``gtdatasource-facets``
   * - ``<name>/export``
     - a file, ``?fmt=csv|xlsx|json|pdf``
     - ``gtdatasource-export``

The parameters go as ``?params=<json>`` on a GET or in a POST body, either
``{"params": {...}}`` or the document itself (in a POST, the facet columns are
``"facets"``). ``rows`` pages with ``offset``/``limit`` (or DataTables'
``start``/``length``, up to ``GT_DATASOURCE_MAX_PAGE_SIZE``, 1000) and also
reads the ``search`` and ``ordering`` that ``formatDataTableParams`` sends.
Every endpoint calls ``has_permission`` and answers **403** when it says no;
an unknown source is a 404 and bad parameters a 400.

Exports
-------

``djgentelella.datasources.export.export(source, request, params, fmt)``
returns the ``HttpResponse``. All formats honour the filters, search, ordering,
``columns``, ``aggregates`` and ``highlights``.

``csv``
    Streamed, a chunk of rows at a time; a header row of labels, UTF-8 with a
    BOM so a spreadsheet opens it right. A text cell that starts with ``=``,
    ``+``, ``-``, ``@``, a tab or a carriage return gets a leading ``'``, so a
    spreadsheet never runs it as a formula (CSV injection); numbers are left
    alone.
``json``
    ``{"source", "columns", "data", "aggregates", "truncated", "limit"}``,
    the rows as the API gives them.
``xlsx``
    One sheet: bold frozen header, typed cells, a totals row with the
    aggregates, and the highlights as conditional formatting (or as fills when
    the rule has no formula form, as for ``fk`` columns). Text that starts
    with ``=`` is stored as text, never as a formula. Control characters
    that XML does not allow (``\x00``-``\x08``, ``\x0b``, ``\x0c``,
    ``\x0e``-``\x1f``) are dropped.
``pdf``
    ``gentelella/datasources/export_pdf.html`` rendered by xhtml2pdf: an A4
    landscape table whose header repeats on every page, the totals at the end
    and "Page N of M" in an ``@page`` frame. Override the template like any
    other; ``GT_DATASOURCE_PDF_MAX_ROWS`` (5000) caps the rows.

JSON and XLSX are built in memory, so ``GT_DATASOURCE_EXPORT_MAX_ROWS``
(50000; ``None`` for no limit) caps their rows: JSON then says
``"truncated": true`` and the sheet ends with a note. The totals are always
those of every row. CSV streams and has no cap.

``EXPORTERS`` maps a format to a function ``(source, request, params) ->
HttpResponse``; add one, or replace one, with the decorator:

.. code:: python

    from djgentelella.datasources.export import register_exporter

    @register_exporter('txt')
    def export_txt(source, request, params):
        ...

Formats that depend on the request
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``EXPORTERS`` holds the formats every request has. A format that only some
requests have -- the PDF layouts of the current application, those the user
may print -- comes from a **resolver**, a callable ``(request) -> {format:
exporter}``:

.. code:: python

    from djgentelella.datasources.export import register_exporter_resolver

    @register_exporter_resolver
    def app_layouts(request):
        return {'pdf:%s' % layout.slug: layout.exporter
                for layout in printable_layouts(request)}

``available_exporters(request)`` is ``EXPORTERS`` plus what every resolver in
``EXPORTER_RESOLVERS`` returns for that request (a resolver's format with the
name of a static one wins), and ``available_formats(request)`` their names
(``csv``, ``xlsx``, ``json``, ``pdf`` first, the others by name). That is
what the API accepts in ``fmt``, what the source endpoint lists
(sorted) in ``formats``, what ``{% gt_datasource_export %}`` offers without
``formats`` and what ``gtCreateDataSourceTable`` shows without ``formats``
(reordered by ``gt_datasource_menu_formats``: ``csv``, ``xlsx``, ``json``,
``pdf`` first, the others by name): a
layout of another application is neither listed nor accepted. A resolver that
raises is logged and adds nothing. ``unregister_exporter_resolver`` takes one
out. To list or check the formats of another Site -- a report subscription of
another application, a job --, pass a request of that Site:
``available_formats(site_request(site, user))``
(``djgentelella.sites.site_request``, see :doc:`sites`).

Taking over the export endpoint
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``GT_DATASOURCE_EXPORT_HANDLER`` is a callable (or its dotted path)
``(request, source, params, fmt) -> HttpResponse | None`` the export endpoint
asks first, once the format is known to exist for the request. A response is
the answer -- a 303 to a background job for a large export, say --, and
``None`` lets the export run as usual:

.. code:: python

    # settings.py
    GT_DATASOURCE_EXPORT_HANDLER = 'myapp.jobs.export_handler'

    # myapp/jobs.py
    def export_handler(request, source, params, fmt):
        if apply_params(source, request, params).count() < 10000:
            return None
        job = start_job('myapp.jobs.export_job', {...}, request.user)
        return redirect(job)

Only the endpoint (``export.handle_export``) calls it: ``export()`` never
does, so the job that exports with it does not come back to the handler.
Before the handler, ``handle_export`` checks the parameters with
``validate_params``: an unknown column or a wrong aggregate is a
``ValidationError`` (a 400 from the API) at once, not an error of the job.

Widgets
-------

``gentelella/js/base/gt_facets.js`` (part of ``base.js``) has a table, two
filter widgets and an export menu. Every widget that names the same source
(and ``group``, if a page has two tables over one source) shares one
parameter document: a facet writes its filter there and the table, the other
facets, the chips and the export menu reload.

.. code:: html+django

    {% load gtdatasources %}
    <div class="row">
      <div class="col-md-3">
        {% gt_facets 'sales.orders' 'status,customer,total,created' %}
      </div>
      <div class="col-md-9">
        {% gt_facet_chips 'sales.orders' 'status,customer' %}
        {% gt_datasource_export 'sales.orders' %}
        <table id="orders" class="table w-100"></table>
      </div>
    </div>

    {% block js %}
    <script>
      gtCreateDataSourceTable('#orders', '{% gt_datasource_url "sales.orders" %}', {
        columns: ['number', 'customer', 'status', 'total', 'created']
      });
    </script>
    {% endblock %}

``gt_facets``
    ``GTFacets``, the side panel: checkboxes with counts for values, radios
    for ranges and periods, and a from/to range under numeric and date
    columns.
``gt_facet_chips``
    ``GTFacetChips``, the "smart filters": the active filters as removable
    chips and a dropdown per column with its values and counts.
``gt_datasource_export``
    ``GTDataSourceExport``, a menu that downloads what the page shows now:
    the formats of the request by default (see `Formats that depend on the
    request`_), ``formats='csv,pdf'`` to restrict it.
``gtCreateDataSourceTable(id, url, options)``
    A server side DataTable built on ``gtCreateDataTable`` from the source's
    columns, with an export button of the formats the source endpoint lists
    (``formats: [...]`` picks them, ``formats: []`` hides it). Options:
    ``columns``, ``group``, ``params`` (a base document) and any
    ``gtCreateDataTable`` option. Returns a promise of the DataTable. Every
    cell is escaped (the ``display_name`` of ``fk`` and ``m2m`` columns
    included) and so are the column titles: values that users write never
    reach the page as HTML.

All three tags take ``group`` and ``params`` too. The widgets are registered
in ``document.gtwidgets``, so markup added later is initialised by
``gt_find_initialize``. After changing the JavaScript, rebuild ``base.js``
with ``python manage.py createbasejs``.

Demo
----

``demoapp/gtdatasources.py`` registers ``demoapp.person`` and
``demoapp.purchases``; the page ``/datasources/`` (menu *Data sources*) shows
the table, the facets, the chips and the export menu over the first.

Tests
-----

``djgentelella/tests/Datasources_Test.py`` runs on SQLite. The full-text
search tests are tagged ``postgresql`` and skip themselves elsewhere; run them
with ``demo/settings_postgres.py``::

    cd demo
    PGHOST=localhost PGPORT=5432 PGUSER=postgres PGPASSWORD=... PGDATABASE=demo \
    DJANGO_SETTINGS_MODULE=demo.settings_postgres \
    python manage.py test djgentelella.tests.Datasources_Test
