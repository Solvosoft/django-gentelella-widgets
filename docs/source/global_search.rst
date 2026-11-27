Global search
=============

One search box that finds objects of several models at once, grouped by type,
showing only what the user may see in the current Site. It is built on the
:doc:`data sources <datasources>`: a searchable source is a registered data
source with a ``global_search`` description, not a second registry of models.
Each source is asked through its own ``get_queryset(request)``, and only when
its ``has_permission(request)`` says yes.

``djgentelella.search`` is a plain package (no models). Its two URLs come with
``djgentelella.urls``:

=====================  =============================  ==================
URL                    name                           what
=====================  =============================  ==================
``search/?q=``         ``gt-search``                  the results page
``gtapis/search/?q=``  ``gt-search-api``              the same, as JSON
=====================  =============================  ==================

Making a data source searchable
-------------------------------

In ``<app>/gtdatasources.py``, next to the source. Either the decorator:

.. code:: python

    from djgentelella.datasources.base import ModelDataSource, register_datasource
    from djgentelella.search import searchable

    @register_datasource
    @searchable(fields={'name': 'A', 'code': 'B', 'region__name': 'C'},
                title='name', subtitle='{code} - {region.name}',
                url='sales_customer_detail', group=_('Customers'),
                icon='fa fa-user')
    class CustomerSource(ModelDataSource):
        model = Customer
        name = 'sales.customers'
        site_field = 'site'

``@searchable`` goes *below* ``@register_datasource`` (it is applied first).
It works on an instance too::

    register_datasource(searchable(fields=['title'], url='page:tickets')(
        ModelDataSource(Ticket, name='help.tickets')))

or the attribute it sets, ``global_search = GlobalSearch(...)``.
``GlobalSearch`` takes:

``fields``
    Where to search: ``{orm_path: weight}`` with weights ``'A'`` (most
    important) to ``'D'``, or a list of paths (all ``'A'``). By default the
    text columns of the source. A path may cross foreign keys
    (``'region__name'``) but not a many-to-many or a reverse relation: they
    would repeat the object, and ``ImproperlyConfigured`` says so.
``title`` / ``subtitle``
    What a hit shows: an ORM path (``'name'``, ``'region__name'``), a format
    string over the object (``'{code} - {name}'``, ``'{region.name}'``) or a
    callable ``(obj) -> str``. The title defaults to ``str(obj)``.
``url``
    Where a hit leads: a URL name reversed with the pk (as ``args`` or as
    ``pk``), ``'page:<path>'`` for a :doc:`design page <designs>` about the
    object (``designs/<path>/<pk>``), a format string that starts with ``/``
    or contains ``{`` (``'/c/{pk}/'``), or a callable ``(obj) -> str``.
    Without it, ``obj.get_absolute_url()`` if the model has one; otherwise the
    hit has no link. A URL that is not relative or ``http(s)`` (a
    ``javascript:`` built from a field, say) is dropped.
``group``
    The label of the group (the source's ``label`` by default), and ``icon``,
    a CSS class shown next to it.
``limit``
    Hits per group (``GT_SEARCH_LIMIT`` by default).
``select_related``
    Relations to load with the hits, for a title or a URL that reads them.
    Foreign keys named by a ``title``/``subtitle`` path or ``{a__b}``
    placeholder are added on their own; a callable or ``{a.b}`` that follows
    a relation needs it here, or it costs a query per hit.
``owners`` / ``tags``
    Who the source belongs to -- the keys of whatever groups sources in the
    project: the slugs of the applications, a tenant -- and free labels
    (``'catalog'``, ``'people'``). A string is one key. Without ``owners``
    the source is shared. djgentelella only keeps them, for a
    ``GT_SEARCH_SOURCES`` hook and for screens that let someone choose
    sources (see "Choosing the sources per request").

What the search does
--------------------

.. code:: python

    from djgentelella.search import search

    groups = search(request, 'costa rica')                 # every searchable source
    groups = search(request, 'costa', sources=['sales.customers'], limit=10)

``search(request, query, sources=None, limit=None, offset=0)`` returns a list
of ``SearchGroup`` (``source``, ``label``, ``icon``, ``results``,
``has_more``, ``score``) with ``SearchResult`` hits (``title``, ``subtitle``,
``url``, ``score``, ``pk``); ``as_dict()`` of each is the JSON of the API.
Groups without hits are left out; the group with the best hit comes first,
and the hits of a group are ordered by relevance, then by pk.

For each searchable source, in order:

#. ``has_permission(request)``: a source the user may not read is **not
   queried**.
#. ``get_queryset(request)``: rows the user may not see (permissions, row
   rules, another Site through ``site_field``) never match. A
   ``PermissionDenied`` from it skips the source.
#. **One query**, with ``limit + 1`` rows to know whether there are more.

The engine depends on the database:

* **PostgreSQL** with ``django.contrib.postgres`` in ``INSTALLED_APPS``:
  full-text search. ``SearchVector`` of the fields with their weights (and the
  source's ``search_config``), ``SearchRank`` as the score. Plain words are
  prefixes, all required (``"cost ric"`` finds Costa Rica while typing);
  quotes, ``or`` and ``-`` use the web search syntax. These are the rules of
  the data source search box.
* **pg_trgm**: if the extension is in the database, a hit also matches when
  the text is similar to a field (``TrigramWordSimilarity`` at least
  ``GT_SEARCH_TRIGRAM_THRESHOLD``), so typos still find (``"nicaruga"``); the
  similarity is added to the score. Without the extension, full-text only.
* **Any other database**, or a source with ``search_mode = 'icontains'``:
  every word must be in one of the fields (``icontains``). The score adds, per
  field, its weight times 4 if it equals the text, 3 if it starts with it, 2 if
  it contains it, plus the weight divided among the words found. Weights are
  worth what ``ts_rank`` gives them (A 1.0, B 0.4, C 0.2, D 0.1). On SQLite
  ``icontains`` ignores case only for ASCII letters.

A source with ``search_mode = 'fulltext'`` on another database falls back to
``icontains`` here (the data source API answers 400 instead): one source must
not break the search of the others.

All of it is ORM; the user's text only reaches the database as a query
parameter. The text is stripped, its blanks collapsed and cut to
``GT_SEARCH_MAX_LENGTH`` characters; shorter than ``GT_SEARCH_MIN_LENGTH``
it finds nothing and costs no query.

Number of queries
^^^^^^^^^^^^^^^^^

One per source the user may read, plus:

* once per process and database, the detection of ``pg_trgm`` (a constant
  query to ``pg_extension``) -- skip it with ``GT_SEARCH_TRIGRAM = True`` or
  ``False``; ``reset_trigram_cache()`` forgets it after installing the
  extension in a running process;
* what ``has_permission`` costs: the default loads the user's permissions
  once per request (Django caches them in the user object).

There is no global timeout: the sources are queried one after another. Keep
the searchable sources to the ones people look for, and see *Indexes* below
for large tables.

pg_trgm
-------

pg_trgm ships with PostgreSQL (``postgresql-contrib``; the official Docker
image has it). Create it by hand::

    CREATE EXTENSION IF NOT EXISTS pg_trgm;

or add the optional app, whose only migration does it:

.. code:: python

    INSTALLED_APPS += ['django.contrib.postgres', 'djgentelella.search.trigram']

The migration needs a role allowed to create the extension (pg_trgm is a
trusted extension since PostgreSQL 13, so the owner of the database can) and
``psycopg``; it does nothing on other databases, and reversing it drops the
extension. Do not add the app to a project that does not run on PostgreSQL.

The results page and the box
----------------------------

``search/?q=<text>`` shows every group with its first hits and, when there are
more, a *See more* link: the same page with ``source=<name>``, which shows
that group alone, ``GT_SEARCH_PAGE_SIZE`` hits per page with previous/next
links. The template is ``gentelella/search/results.html``.

The page extends ``GT_SEARCH_BASE_TEMPLATE`` (``gentelella/base.html``).
Inside an application with a layout of its own, ``GT_SEARCH_PAGE_CONTEXT``
is the dotted path of a callable ``(request) -> dict`` whose keys are added
to the page's context: a ``base_template`` of its own, ``breadcrumbs``
(gentelella's breadcrumbs block draws them), a theme. It cannot replace what
the page itself shows (``query``, ``source``, ``groups``, the pages...)::

    def search_context(request):
        app = getattr(request, 'app', None)
        if app is None:
            return {}
        return {'base_template': app.base_template,
                'breadcrumbs': [{'label': app.title, 'href': app.url},
                                {'label': _('Search'), 'href': ''}]}

The box in the top bar is off by default. Turn it on for the whole project::

    GT_SEARCH_NAVBAR = True

or for one Site, with its ``global_search`` setting (``"true"`` or
``"false"``), which wins over ``GT_SEARCH_NAVBAR``::

    from djgentelella.search import NAVBAR_SETTING   # 'global_search'
    from djgentelella.utils import set_settings
    set_settings(NAVBAR_SETTING, 'true', site=site)

The box sends the form to the results page; while typing, it asks the JSON
API and lists the hits under it (arrow keys, Enter, Escape). It is drawn by
``{% global_search_box %}`` (``{% load gtsearch %}``) in
``gentelella/app/top_navigation.html``; a project with its own top bar can
place it elsewhere, and ``{% global_search_box force=True %}`` draws it
regardless of the settings. The script is
``static/gentelella/js/globalsearch.js``, with no dependencies.

The JSON API
------------

``GET gtapis/search/?q=<text>[&sources=a,b][&limit=n][&offset=n]``::

    {"query": "panama",
     "groups": [{"source": "demoapp.country", "label": "Countries",
                 "icon": "fa fa-flag", "has_more": false,
                 "more_url": "/search/?q=panama&source=demoapp.country",
                 "results": [{"title": "Panama", "subtitle": "pa",
                              "url": "/demoapp/country/2", "score": 4.0,
                              "pk": "2"}]}]}

``limit`` is capped at ``GT_SEARCH_MAX_LIMIT``; values that are not numbers
are ignored. Neither the page nor the API requires a session: an anonymous
request finds what the sources open to anyone (``perms = []``) contain, which
by default is nothing.

Choosing the sources per request
--------------------------------

``GT_SEARCH_SOURCES`` is the dotted path of a callable ``(request) -> list of
source names or None``. The page, the API and ``search()`` without
``sources`` search only those (``None``: all). The page and the API also keep
an explicit ``source``/``sources`` within that list. A project with several
applications (Sites) uses it to search, in each one, its own sources.

The owners of the sources (``owners`` of ``GlobalSearch``) are what such a
hook reads: ``searchable_sources(owner=...)`` keeps the shared sources and
those of that owner (``owner=None``: only the shared ones), and ``tags=``
those with every given tag. ``source_owners(source)``, ``source_tags(source)``
and ``is_owned_by(source, owner)`` answer for one source::

    from djgentelella.search import searchable_sources

    def app_sources(request):
        app = getattr(request, 'app', None)
        return list(searchable_sources(owner=app.slug if app else None))

    GT_SEARCH_SOURCES = 'myproject.search.app_sources'

Settings
--------

=================================  ========  ==========================================
Setting                            Default   Meaning
=================================  ========  ==========================================
``GT_SEARCH_NAVBAR``               False     the box in the top bar
``GT_SEARCH_LIMIT``                5         hits per group
``GT_SEARCH_PAGE_SIZE``            20        hits per page of one group ("see more")
``GT_SEARCH_MAX_LIMIT``            50        the largest ``limit`` of the API
``GT_SEARCH_MIN_LENGTH``           2         shorter texts do not search
``GT_SEARCH_MAX_LENGTH``           200       longer texts are cut
``GT_SEARCH_TRIGRAM``              None      pg_trgm: None detects it, True/False force
``GT_SEARCH_TRIGRAM_THRESHOLD``    0.5       least word similarity of a trigram hit
``GT_SEARCH_SOURCES``              None      callable choosing the sources of a request
``GT_SEARCH_BASE_TEMPLATE``        (base)    the template the results page extends
``GT_SEARCH_PAGE_CONTEXT``         None      callable adding context to the results page
=================================  ========  ==========================================

Indexes
-------

The search computes the vectors on the fly, which is fine for thousands of
rows per source. For large tables the usual next step -- not done by
djgentelella -- is an index per source: a ``GinIndex`` over the same
``SearchVector`` expression (with the same ``config``), a ``SearchVectorField``
kept up to date by a trigger, or a ``GinIndex(opclasses=['gin_trgm_ops'])``
for the trigram similarity. External engines (Elasticsearch, Meilisearch) are
out of scope.

API
---

.. automodule:: djgentelella.search.base
   :members: GlobalSearch, searchable, searchable_sources

.. automodule:: djgentelella.search.engine
   :members: search, search_source, SearchGroup, SearchResult,
             trigram_available, reset_trigram_cache
