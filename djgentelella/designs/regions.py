"""Region components: the rows of a data source as cards, on a calendar or
on a map (``cards``, ``calendar`` and ``map``).

The three share one contract (C15): where the rows come from, which column
plays each role, the row links and the conditions.

``datasource``      a registered data source (:mod:`djgentelella.datasources`):
                    its ``get_queryset(request)`` -- Site and permissions -- is
                    every row the component shows; or
``model``           an exposed model, with ``site_field`` (a foreign key to
                    ``sites.Site``) to show only the current Site's rows and
                    the global ones. The rows are those of a
                    ``ModelDataSource`` over the fields its exposure allows.
``title_field``     the role columns: ``subtitle_field``, ``image_field``
                    (cards), ``start_field``/``end_field``/``color_field``
                    (calendar), ``point_field`` (map, a ``GTPointField``:
                    ``"lat,lng"``)
``fields``          more columns shown on the card or in the popup
``row_links``       links to pages about one row, as a table's; the first one
                    is the row's own link: clicking the card's title, the
                    calendar event or the link of the popup opens it
``column_conditions``  ``{field: condition}``: a field shown only when its
                    condition holds; the API also refuses to filter by it
``perms``           what seeing it needs; a data source checks its own

A node condition (``props.condition``) hides the whole component and its
endpoint (the engine does it), and each row link has its own condition.

Facets: a ``facets`` panel may name one of these nodes as its ``target`` when
it reads a ``datasource``: the panel and the component share the data source
state of the page (``gtdesign:<node id>``), and the component reloads with the
panel's filters, sent as the query parameter document (``?params=``).

Each node serves ``gtapis/designs/<page>/<node>/``:

* ``cards``: ``?page=&page_size=&params=`` -- the JSON of
  :class:`~djgentelella.views.listAreaViewset.ListAreaViewset` (``data``,
  ``recordsTotal``, ``totalPages``, ``currentPage``, ``template``), read by
  the ``CardList`` of the browser;
* ``calendar``: ``?start=&end=&params=`` -- ``{"events": [...],
  "truncated": bool}``, only the rows of that range (FullCalendar asks for
  the visible one), at most ``limit``;
* ``map``: ``?bbox=<west>,<south>,<east>,<north>&params=`` -- the payload
  of :class:`~djgentelella.views.maps.BaseMapView` (``DJMap``), with
  ``truncated``: the points inside the box, at most ``limit``.

Without the permissions of the build or of the data source the endpoint
answers 403.
"""

import datetime
import re
from dataclasses import dataclass, field
from urllib.parse import quote

from django.core.exceptions import FieldDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.db.models import Case, FloatField, Q, Value, When
from django.db.models.functions import Cast, Left, StrIndex, Substr, Trim
from django.http import Http404
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import NoReverseMatch, reverse
from django.utils import formats, timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.safestring import mark_safe
from django.utils import translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from djgentelella.datasources import query
from djgentelella.datasources.base import (
    ModelDataSource, get_datasource, project_model_of, resolve_field_path,
)
from djgentelella.designs.builds import DataBuild
from djgentelella.designs.components import (
    Endpoint, ResolveContext, RuntimeComponent,
)
from djgentelella.designs.conditions import (
    check_conditions, conditions_schema, hidden_columns,
)
from djgentelella.designs.data_components import (
    PERMISSION_LIST, allowed_fields, can, data_build, endpoint_url, find_node,
    json_config, kind_of, no_permission, plural, resolve_row_links,
    row_link_config, source_columns,
)
from djgentelella.fields.maps import GTPointField, parse_point
from djgentelella.permission_management import all_permission
from djgentelella.serializers.paginators import PageListPagination
from djgentelella.views.listAreaViewset import ListAreaViewset
from djgentelella.views.maps import BaseMapView

__all__ = ['CALENDAR_VIEWS', 'CalendarBuild', 'CalendarComponent',
           'CalendarViewSet', 'CardsBuild', 'CardsComponent', 'CardsViewSet',
           'MapBuild', 'MapComponent', 'MapViewSet', 'REGION_COMPONENTS',
           'RegionBuild', 'RegionComponent', 'RegionMixin', 'check_access',
           'events_in_range', 'map_points', 'read_rows', 'region_page_context',
           'region_queryset', 'region_source', 'request_params']

SCRIPT = 'gentelella/js/designs/regions.js'
FULLCALENDAR = 'vendors/fullcalendar/index.global.min.js'
#: Every FullCalendar locale (``@fullcalendar/core``), ~26 KB.
FULLCALENDAR_LOCALES = 'vendors/fullcalendar/locales-all.global.min.js'
MARKERCLUSTER = ('vendors/leaflet-markercluster/leaflet.markercluster.js',
                 'vendors/leaflet-markercluster/MarkerCluster.css',
                 'vendors/leaflet-markercluster/MarkerCluster.Default.css')
#: What a role or a shown field cannot be.
NOT_SHOWN = ('json', 'binary')
DATE_KINDS = ('date', 'datetime')
CALENDAR_VIEWS = ('dayGridMonth', 'timeGridWeek', 'timeGridDay', 'listMonth')
#: A CSS colour the calendar may paint an event with: ``#rgb[a]``,
#: ``#rrggbb[aa]`` or a colour name. Anything else is dropped.
COLOR = re.compile(r'^(#[0-9a-fA-F]{3,4}|#[0-9a-fA-F]{6}|#[0-9a-fA-F]{8}'
                   r'|[a-zA-Z]{3,20})$')
COLOR_SCHEMA = {'type': 'string', 'pattern': COLOR.pattern}
#: The widest range the calendar endpoint answers, in days: a month view asks
#: for six weeks, a list of a year for a bit more than 366 days.
MAX_RANGE_DAYS = 400
#: ``"lat,lng"`` as the database sees it (``GTPointField``).
POINT_RE = r'^\s*-?[0-9]+(\.[0-9]+)?\s*,\s*-?[0-9]+(\.[0-9]+)?\s*$'
#: The defaults and the largest values of ``limit`` and ``page_size``.
CARDS_PAGE_SIZE, CARDS_MAX_PAGE_SIZE = 12, 100
CALENDAR_LIMIT, CALENDAR_MAX_LIMIT = 500, 2000
MAP_LIMIT, MAP_MAX_LIMIT = 500, 5000


@dataclass
class RegionBuild(DataBuild):
    """What the three region components have (C15)."""

    #: The model of the rows: the prop, or the data source's (may be None for
    #: a data source that is not over a model).
    model: type = None
    #: Name of a registered data source, or ``''`` for ``model``.
    datasource: str = ''
    #: With ``model``: a foreign key to ``sites.Site``.
    site_field: str = ''
    #: With ``model``: the columns of the data source made over it (those the
    #: exposure allows).
    source_fields: list = field(default_factory=list)
    #: ``app.codename`` the user needs, every one; ``[]``: only the data
    #: source's own check.
    perms: list = field(default_factory=list)
    title_field: str = ''
    subtitle_field: str = ''
    #: More columns shown (card body, popup).
    fields: list = field(default_factory=list)
    #: ``{column: label}`` and ``{column: kind}`` of every column it reads.
    labels: dict = field(default_factory=dict)
    kinds: dict = field(default_factory=dict)
    #: ``{column: True}`` of the columns over a file field: shown by URL.
    files: dict = field(default_factory=dict)
    #: ``{column: {str(value): label}}`` of the columns with choices.
    choices: dict = field(default_factory=dict)
    row_links: list = field(default_factory=list)
    column_conditions: dict = field(default_factory=dict)
    ordering: list = field(default_factory=list)
    #: The data source state of the page it follows (``gtdesign:<node>``):
    #: its own, or that of the target of the facets panel ``filtered_by``.
    group: str = ''

    def read_columns(self):
        """Every column a row is read with, each once."""
        names = [self.title_field, self.subtitle_field] + list(self.fields)
        return [name for name in dict.fromkeys(names) if name]


@dataclass
class CardsBuild(RegionBuild):
    image_field: str = ''
    page_size: int = CARDS_PAGE_SIZE
    #: Cards per row on a wide screen (1, 2, 3, 4 or 6).
    per_row: int = 3
    search: bool = True

    def read_columns(self):
        names = super().read_columns()
        if self.image_field and self.image_field not in names:
            names.append(self.image_field)
        return names


@dataclass
class CalendarBuild(RegionBuild):
    start_field: str = ''
    end_field: str = ''
    color_field: str = ''
    #: ``{value of color_field: colour}``.
    colors: dict = field(default_factory=dict)
    #: ``[{"filter": <C4 filter>, "color": ...}]``: the first that matches.
    color_rules: list = field(default_factory=list)
    initial_view: str = 'dayGridMonth'
    limit: int = CALENDAR_LIMIT

    def read_columns(self):
        names = super().read_columns()
        for name in (self.start_field, self.end_field, self.color_field):
            if name and name not in names:
                names.append(name)
        return names


@dataclass
class MapBuild(RegionBuild):
    point_field: str = ''
    cluster: bool = False
    limit: int = MAP_LIMIT
    #: Load the points of the visible box again when the map moves.
    bbox: bool = True
    center: list = None
    zoom: int = None
    height: int = 420

    def read_columns(self):
        names = super().read_columns()
        if self.point_field not in names:
            names.append(self.point_field)
        return names


# -- the rows ------------------------------------------------------------------------

def region_source(build):
    """The data source of the rows of ``build``: its ``datasource``, or a
    ``ModelDataSource`` over its model (with its ``site_field`` and
    ``perms``). ``None`` when the data source is gone."""
    if build.datasource:
        try:
            return get_datasource(build.datasource)
        except (KeyError, LookupError):
            return None
    return ModelDataSource(build.model, name='gtdesign.%s' % build.id,
                           fields=list(build.source_fields), perms=list(build.perms),
                           site_field=build.site_field or None)


def check_access(build, request):
    """The data source of ``build`` if ``request`` may read it: 403
    (``PermissionDenied``) without the build's permissions or the source's,
    404 when the data source is gone.

    The contract of the 403 of every region endpoint: ``build.perms`` (all
    of them) and then :func:`region_source` ``.has_permission(request)``.
    :func:`region_page_context` applies the same rule to the page."""
    if build.perms and not all_permission(request.user, list(build.perms)):
        raise PermissionDenied()
    source = region_source(build)
    if source is None:
        raise Http404()
    if not source.has_permission(request):
        raise PermissionDenied()
    return source


def request_params(build, request, hidden=()):
    """The query parameter document of the request (``?params=``), without
    the parts a region does not use; 400 on a filter or an ordering over a
    hidden column."""
    try:
        params = query.parse_params(request.query_params.get('params'))
    except DjangoValidationError as error:
        raise ValidationError({'detail': error.messages})
    search = request.query_params.get('search')
    if search and not params['search']:
        params['search'] = search
    names = [flt.get('column') for flt in params['filters']]
    names += [str(item).lstrip('-') for item in params['ordering']]
    if any(str(name).split('__')[0] in hidden for name in names if name):
        raise ValidationError({'detail': _('unknown column')})
    return {'search': params['search'], 'filters': params['filters'],
            'ordering': params['ordering'] or list(build.ordering)}


def region_queryset(build, source, request, params):
    """``apply_params`` of the source -- its ``get_queryset(request)``, the
    filters, the search and the ordering -- or 400."""
    try:
        return query.apply_params(source, request, params)
    except DjangoValidationError as error:
        raise ValidationError({'detail': error.messages})


def file_url(model_field, name):
    try:
        return model_field.storage.url(name)
    except Exception:  # noqa: BLE001 -- a storage that cannot say: no image
        return ''


def safe_url(value):
    """``value`` if it is a link within the site or to http(s), else ''."""
    value = str(value or '')
    return value if re.match(r'^(https?://|/(?!/))', value, re.IGNORECASE) else ''


def display(build, name, value):
    """The text of ``value`` of column ``name``, as ``serialize_rows``
    reads it: a relation is ``{id, display_name}``, a many-to-many a list of
    them."""
    if value is None or value == '':
        return ''
    if isinstance(value, dict):
        return str(value.get('display_name', ''))
    if isinstance(value, list):
        return ', '.join(display(build, name, item) for item in value)
    if name in build.choices:
        return str(build.choices[name].get(str(value), value))
    kind = build.kinds.get(name)
    if kind == 'boolean':
        return _('Yes') if value else _('No')
    if isinstance(value, datetime.datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return formats.date_format(value, 'SHORT_DATETIME_FORMAT')
    if isinstance(value, datetime.date):
        return formats.date_format(value, 'SHORT_DATE_FORMAT')
    if kind in ('integer', 'decimal'):
        return formats.localize(value, use_l10n=True)
    return str(value)


def read_rows(build, source, request, queryset):
    """The rows of ``queryset`` as dicts by column (``pk`` too), in the
    queryset's order: raw values, the relations as ``{id, display_name}``."""
    colmap = source.column_map(request)
    columns = [colmap[name] for name in build.read_columns() if name in colmap]
    return query.serialize_rows(source, request, queryset, columns)


def model_field_of(model, name):
    """The model field at the end of the path ``name``, or None."""
    if model is None:
        return None
    try:
        return resolve_field_path(model, name)[0]
    except (FieldDoesNotExist, AttributeError):
        return None


def link_urls(build, request):
    """``[(RowLink, url, placeholder)]`` of the row links whose condition
    holds for ``request``."""
    result = []
    for config in row_link_config(build, request):
        index = int(config['name'][len('link'):])
        result.append((build.row_links[index], config['url'], config['placeholder']))
    return result


def row_url(url, placeholder, pk):
    return url.replace(placeholder, quote(str(pk), safe=''))


def row_texts(build, row, hidden):
    """``{'title', 'subtitle', 'fields': [{'label', 'value'}]}`` of a row."""
    shown = [name for name in build.fields if name not in hidden]
    return {
        'title': display(build, build.title_field, row.get(build.title_field))
        if build.title_field else str(row.get('pk')),
        'subtitle': '' if not build.subtitle_field or build.subtitle_field in hidden
        else display(build, build.subtitle_field, row.get(build.subtitle_field)),
        'fields': [{'label': build.labels.get(name, name),
                    'value': display(build, name, row.get(name))} for name in shown],
    }


def row_links(links, pk):
    return [{'title': str(link.title), 'icon': link.icon,
             'url': row_url(url, placeholder, pk)} for link, url, placeholder in links]


# -- the components ------------------------------------------------------------------

ROW_LINKS_SCHEMA = {
    'type': 'array',
    'x-widget': 'links',
    'title': 'Row links to pages about one row (the first one opens it)',
    'items': {
        'type': 'object',
        'required': ['url_name', 'title'],
        'additionalProperties': False,
        'properties': {'url_name': {
                           'type': 'string', 'minLength': 1,
                           'description': 'A URL name taking the row pk, '
                           '"page:<path>" or "flow:<name>"[":<transition>"]'},
                       'title': {'type': 'string'},
                       'icon': {'type': 'string'},
                       'condition': {'x-widget': 'condition',
                                     'title': 'Shown only when'}},
    },
}


def column_prop(title, x_filter=None):
    schema = {'type': 'string', 'x-widget': 'model-field', 'title': title}
    if x_filter:
        schema['x-filter'] = x_filter
    return schema


def common_properties():
    """The props every region component takes (C15)."""
    return {
        'model': {'type': 'string', 'x-widget': 'model', 'title': 'Model'},
        'datasource': {'type': 'string', 'x-widget': 'datasource',
                       'title': 'Data source (instead of a model)'},
        'site_field': {'type': 'string', 'x-widget': 'model-field',
                       'x-filter': 'site',
                       'title': "Foreign key to the Site (only the current Site's "
                                'rows; with a model)'},
        'title': {'type': 'string', 'title': 'Title'},
        'title_field': column_prop('Title of each row'),
        'subtitle_field': column_prop('Subtitle of each row'),
        'fields': {'type': 'array', 'items': {'type': 'string'},
                   'x-widget': 'model-fields', 'title': 'More fields shown'},
        'ordering': {'type': 'array', 'items': {'type': 'string'},
                     'title': 'Ordering (e.g. -pk)'},
        'row_links': ROW_LINKS_SCHEMA,
        'column_conditions': conditions_schema('Fields shown only when (by field)'),
        'filtered_by': {'type': 'string', 'x-widget': 'node', 'x-filter': 'facets',
                        'title': 'Also filtered by this facets panel (over the '
                                 'same data source)'},
        'perms': {**PERMISSION_LIST, 'x-widget': 'perms',
                  'title': 'Permissions to see it (empty = the model view, or '
                           "only the data source's own)"},
    }


class RegionComponent(RuntimeComponent):
    """Base of ``cards``, ``calendar`` and ``map``: the rows of a data source
    (or of an exposed model) with columns by role."""

    build_class = RegionBuild
    template = ''
    #: A facets panel may filter it, over its ``datasource``.
    facets_target = True
    #: ``{prop: (title, allowed kinds or None, required)}`` of the role
    #: columns besides title and subtitle.
    roles = {}

    def facets_source(self, node, rctx, path):
        name = (node.get('props') or {}).get('datasource')
        if not name:
            rctx.error(path, _('node %r reads a model: a facets panel filters a '
                               'component over a "datasource"') % (node.get('id'),))
            return None
        return name

    # -- resolve ---------------------------------------------------------------------

    def resolve(self, node, rctx, path):
        props = node.get('props') or {}
        build = data_build(self.build_class, node, rctx)
        columns = self.resolve_rows(build, props, rctx, path)
        if columns is None:
            return build
        self.resolve_columns(build, props, rctx, path, columns)
        self.resolve_more(build, props, rctx, path, columns)
        if build.model is not None:
            build.row_links = resolve_row_links(rctx, path, build.model,
                                                props.get('row_links') or [])
        elif props.get('row_links'):
            rctx.error(path + '.props.row_links',
                       _('row links need a data source over a model'))
        self.resolve_group(build, props, rctx, path)
        build.column_conditions = check_conditions(
            rctx, path + '.props.column_conditions', props.get('column_conditions'),
            list(build.fields) + ([build.subtitle_field] if build.subtitle_field
                                  else []), _('shown field'))
        if rctx.has_errors_under(path):
            # Nothing is served from a node with errors: no model, no endpoint.
            build.model, build.datasource = None, ''
        return build

    def resolve_group(self, build, props, rctx, path):
        """The facets it follows: its own panel's (one whose ``target`` is
        this node) or, with ``filtered_by``, the panel of another node over
        the same data source."""
        build.group = 'gtdesign:%s' % build.id
        panel_id = props.get('filtered_by')
        if not panel_id:
            return
        where = path + '.props.filtered_by'
        panel = find_node(rctx.design, panel_id)
        if panel is None or panel.get('type') != 'facets':
            rctx.error(where, _('%r is not the id of a facets panel of this page')
                       % (panel_id,))
            return
        target_id = (panel.get('props') or {}).get('target')
        target = find_node(rctx.design, target_id) if target_id else None
        source = ((target or {}).get('props') or {}).get('datasource')
        if not build.datasource or source != build.datasource:
            rctx.error(where, _('facets panel %(panel)r filters another data source '
                                'than %(source)r') % {'panel': panel_id,
                                                      'source': build.datasource})
            return
        build.group = 'gtdesign:%s' % target_id

    def depends_on(self, build):
        """The node whose facets it follows: hidden by a condition, its
        filters are not there either."""
        own = 'gtdesign:%s' % build.id
        return [build.group.split(':', 1)[1]] if build.group and \
            build.group != own else []

    def resolve_rows(self, build, props, rctx, path):
        """Model or data source; ``{name: Column}`` of what it offers, or
        ``None`` after an error."""
        has_model, has_source = bool(props.get('model')), bool(props.get('datasource'))
        if has_model == has_source:
            rctx.error(path + '.props', _('give a "model" or a "datasource", not both'))
            return None
        if has_source:
            if props.get('site_field'):
                rctx.error(path + '.props.site_field',
                           _('a data source applies its own Site rule: site_field '
                             'goes with a model'))
            source = rctx.datasource(props['datasource'], path + '.props.datasource')
            if source is None:
                return None
            build.datasource = props['datasource']
            build.model = project_model_of(source)
            if props.get('perms'):
                rctx.check_permissions(path + '.props.perms', props['perms'])
                build.perms = list(props['perms'])
            build.title = props.get('title') or str(source.get_label())
            columns = source_columns(source, rctx, path)
            if columns is None:
                rctx.error(path + '.props.datasource',
                           _('the columns of data source %r cannot be read')
                           % (props['datasource'],))
            return columns
        found = rctx.exposure(props['model'], path + '.props.model')
        if found is None:
            return None
        model = found.model
        by_name = allowed_fields(found)
        names = [name for name, model_field in by_name.items()
                 if kind_of(model_field) not in ('binary',)]
        site_field = props.get('site_field') or ''
        if site_field:
            model_field = next((item for item in model._meta.get_fields()
                                if item.name == site_field), None)
            related = getattr(model_field, 'related_model', None)
            if model_field is None or not model_field.many_to_one or \
                    related is None or related._meta.label_lower != 'sites.site':
                rctx.error(path + '.props.site_field',
                           _('%(field)r is not a foreign key of %(model)s to '
                             'sites.Site') % {'field': site_field,
                                              'model': model._meta.label})
        perms = props.get('perms') or found.permissions('view')
        rctx.check_permissions(path + '.props.perms', perms)
        build.model = model
        build.site_field = site_field
        build.source_fields = names
        build.perms = list(perms)
        build.title = props.get('title') or plural(model)
        source = ModelDataSource(model, name='gtdesign.%s' % build.id, fields=names,
                                 perms=[])
        return source.column_map(None)

    def check_column(self, build, rctx, where, columns, name, kinds=None):
        """Whether ``name`` is a column the rows offer (of ``kinds``)."""
        column = columns.get(name)
        if column is None or column.kind in NOT_SHOWN:
            rctx.error(where, _('%r is not a column of the rows this component '
                                'may show') % (name,))
            return False
        if kinds is not None and column.kind not in kinds:
            rctx.error(where, _('%(column)r is not a %(what)s column') % {
                'column': name, 'what': ' / '.join(kinds)})
            return False
        build.labels[name] = str(column.label)
        build.kinds[name] = column.kind
        model_field = model_field_of(build.model, name)
        if isinstance(model_field, models.FileField):
            build.files[name] = True
        if column.choices:
            build.choices[name] = {str(value): str(text)
                                   for value, text in column.choices}
        return True

    def resolve_columns(self, build, props, rctx, path, columns):
        for prop in ('title_field', 'subtitle_field'):
            name = props.get(prop)
            if name and self.check_column(build, rctx, '%s.props.%s' % (path, prop),
                                          columns, name):
                setattr(build, prop, name)
        for prop, (kinds, required) in self.roles.items():
            name = props.get(prop)
            where = '%s.props.%s' % (path, prop)
            if not name:
                if required:
                    rctx.error(where, _('%s is required') % prop)
                continue
            if self.check_column(build, rctx, where, columns, name, kinds):
                setattr(build, prop, name)
        fields = props.get('fields') or []
        if len(set(fields)) != len(fields):
            rctx.error(path + '.props.fields', _('a field is listed twice'))
        for index, name in enumerate(fields):
            self.check_column(build, rctx, '%s.props.fields[%d]' % (path, index),
                              columns, name)
        build.fields = [name for name in dict.fromkeys(fields) if name in build.kinds]
        ordering = props.get('ordering') or []
        for index, name in enumerate(ordering):
            bare = str(name).lstrip('-')
            column = columns.get(bare)
            if bare != 'pk' and (column is None or not column.sortable):
                rctx.error('%s.props.ordering[%d]' % (path, index),
                           _('unknown field %r') % (name,))
        build.ordering = list(ordering)

    def resolve_more(self, build, props, rctx, path, columns):
        """The props of one type of region; ``columns`` as
        :meth:`resolve_rows` returns them."""

    # -- render ----------------------------------------------------------------------

    def render(self, build, rctx, children):
        if build.model is None and not build.datasource:
            return mark_safe('')
        if rctx.preview:
            return render_to_string(self.template, {
                'b': build, 'preview': True, 'sample': self.sample(build)})
        context = self.page_context(build, rctx, endpoint_url(rctx, build))
        if context is None:
            return no_permission(build)
        return render_to_string(self.template, context)

    def page_context(self, build, rctx, url):
        """What :attr:`template` needs to draw ``build`` for the request of
        ``rctx``, its endpoint at ``url``: ``{'b', 'preview', 'template',
        'config'}``; ``None`` when the request may not see it (the rule of
        :func:`check_access`) or there is no ``url``."""
        if build.model is None and not build.datasource:
            return None
        if build.perms and not can(rctx, build.perms):
            return None
        source = region_source(build)
        if source is None or rctx.request is None or \
                not source.has_permission(rctx.request):
            return None
        if not url:
            return None
        config = {'id': build.id, 'type': build.type, 'url': url}
        if build.datasource:
            try:
                config['datasource_url'] = reverse('gtdatasource',
                                                   kwargs={'name': build.datasource})
                config['group'] = build.group or 'gtdesign:%s' % build.id
            except NoReverseMatch:
                pass
        config.update(self.config(build, rctx))
        return {'b': build, 'preview': False, 'template': self.template,
                'config': json_config(build.id + '_gtconfig', config)}

    def config(self, build, rctx):
        return {}

    def sample(self, build):
        return [{'title': '%s %d' % (build.labels.get(build.title_field)
                                     or _('Row'), index),
                 'subtitle': build.labels.get(build.subtitle_field, ''),
                 'fields': [{'label': build.labels.get(name, name),
                             'value': '%s %d' % (_('Value'), index)}
                            for name in build.fields]}
                for index in range(1, 4)]

    def media(self, build, rctx):
        return {'js': [SCRIPT]}

    def endpoints(self, build):
        if build.model is None and not build.datasource:
            return []
        return [Endpoint('', self.viewset, 'gtdesign-%s' % build.id)]


def region_page_context(build, request, url, *, component=None):
    """What the template of a region component needs to draw ``build`` for
    ``request``: ``{'b', 'preview', 'template', 'config'}``, with ``url``
    the URL of its endpoint -- a :class:`CardsViewSet`, :class:`CalendarViewSet`
    or :class:`MapViewSet` (or any :class:`RegionMixin`) serving ``build`` --
    and ``config`` the ``<script>`` the browser reads (``data-gtconfig``):
    ``id``, ``type``, ``url``, with a ``datasource`` its ``datasource_url``
    and ``group`` (the facets it follows), and what the component adds
    (:meth:`RegionComponent.config`).

    No published :class:`~djgentelella.designs.models.Page` is needed: code
    generated from a design (djgentelella-editor) calls it with its own
    build and URL, and includes ``template``. ``None`` when ``request`` may
    not see it -- without ``build.perms``, without the data source or its
    ``has_permission`` (the rule of :func:`check_access`, the one of the
    endpoint's 403) -- or without ``url``.

    ``component`` is the :class:`RegionComponent` of ``build.type``; by
    default the registered one.
    """
    if component is None:
        # The registry imports this module.
        from djgentelella.designs import registry  # noqa: PLC0415 (circular)
        component = registry.get_component(build.type)
        if component is None:
            raise LookupError('no component of type %r' % (build.type,))
    if request is None or build.preview:
        return None
    return component.page_context(build, ResolveContext({}, request), url)


# -- serving -------------------------------------------------------------------------

class RegionMixin:
    """What the region endpoints share: the build of the node, its
    permissions and its rows.

    The build is :meth:`get_build`'s: :attr:`region_build` when a subclass
    sets it -- code generated from a design (djgentelella-editor) does --,
    else ``request.gtdesign_build``, which the endpoint of a published page
    sets; without either, 404."""

    authentication_classes = (SessionAuthentication,)
    permission_classes = (AllowAny,)
    renderer_classes = (JSONRenderer,)
    #: The :class:`RegionBuild` served, for a viewset outside the design
    #: engine; ``None``: the one of the request (``request.gtdesign_build``).
    region_build = None

    def get_build(self):
        """The :class:`RegionBuild` served: :attr:`region_build`, else
        ``request.gtdesign_build``; 404 without either."""
        if self.region_build is not None:
            return self.region_build
        build = getattr(self.request, 'gtdesign_build', None)
        if build is None:
            raise Http404()
        return build

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.build = self.get_build()
        if self.build.preview:
            raise Http404()
        self.source = check_access(self.build, request)
        self.hidden = hidden_columns(self.build, request)
        self.params = request_params(self.build, request, self.hidden)

    def rows_queryset(self):
        return region_queryset(self.build, self.source, self.request, self.params)


class CardsPagination(PageListPagination):
    page_size = CARDS_PAGE_SIZE
    max_page_size = CARDS_MAX_PAGE_SIZE


class CardsViewSet(RegionMixin, ListAreaViewset):
    """The cards of a ``cards`` node: a
    :class:`~djgentelella.views.listAreaViewset.ListAreaViewset`, so the
    browser reads it with ``CardList`` (``api_list.js``)."""

    pagination_class = CardsPagination
    filter_backends = ()
    template_name = 'gtdesigns/components/cards_list.html'
    pagination_top = False
    with_actions = True

    def get_html_id(self):
        return '%s_cards' % self.build.id

    def get_page_size_options(self, request):
        options = super().get_page_size_options(request)
        return [option for option in options
                if option['id'] <= CARDS_MAX_PAGE_SIZE or option['selected']]

    def list(self, request, *args, **kwargs):
        build = self.build
        self.paginator.page_size = build.page_size
        queryset = self.rows_queryset()
        # A page of pks first (with the count), then the rows of that page:
        # the same queries for 1 card or 100.
        pks = self.paginate_queryset(queryset.values_list('pk', flat=True))
        rows = {row['pk']: row for row in read_rows(
            build, self.source, request, queryset.filter(pk__in=list(pks)))}
        links = link_urls(build, request)
        cards = []
        for pk in pks:
            row = rows.get(pk)
            if row is None:
                continue
            card = {'id': pk, **row_texts(build, row, self.hidden),
                    'links': row_links(links, pk), 'image': ''}
            card['url'] = card['links'][0]['url'] if card['links'] else ''
            if build.image_field and build.image_field not in self.hidden:
                value = row.get(build.image_field)
                if build.files.get(build.image_field) and value:
                    value = file_url(model_field_of(build.model, build.image_field),
                                     value)
                card['image'] = safe_url(value)
            cards.append(card)
        data = self.get_paginated_response(cards).data
        data.update(self.template_response(request))
        return Response(data)

    def get_template_context(self, request):
        context = super().get_template_context(request)
        context['col'] = {1: 12, 2: 6, 3: 4, 4: 3, 6: 2}.get(self.build.per_row, 4)
        return context


class CalendarViewSet(RegionMixin, viewsets.ViewSet):
    """The events of a ``calendar`` node between ``?start`` and ``?end``."""

    def list(self, request, *args, **kwargs):
        start, end = visible_range(request.query_params)
        events, truncated = events_in_range(self.build, self.source, request,
                                            self.rows_queryset(), start, end,
                                            self.hidden)
        return Response({'events': events, 'truncated': truncated})


class MapViewSet(RegionMixin, BaseMapView):
    """The points of a ``map`` node: a
    :class:`~djgentelella.views.maps.BaseMapView`, so its payload is the one
    ``DJMap`` and ``maplib.js`` draw."""

    def get_layers(self):
        points, self.truncated = map_points(
            self.build, self.source, self.request, self.rows_queryset(),
            parse_bbox(self.request.query_params.get('bbox')), self.hidden)
        return [{'name': '', 'points': points}]

    def get_cluster(self):
        return self.build.cluster

    def get_fit_bounds(self):
        return not self.request.query_params.get('bbox')

    def list(self, request, format=None):
        response = super().list(request, format)
        response.data['truncated'] = self.truncated
        response.data['limit'] = self.build.limit
        return response


# -- calendar ------------------------------------------------------------------------

def parse_moment(text):
    """An aware datetime of an ISO date or date-time, or None."""
    if not text:
        return None
    text = str(text).strip().replace(' ', '+')
    try:
        moment = parse_datetime(text)
        if moment is None:
            day = parse_date(text)
            if day is None:
                return None
            moment = datetime.datetime.combine(day, datetime.time())
    except ValueError:
        return None
    if timezone.is_naive(moment):
        moment = timezone.make_aware(moment)
    return moment


def visible_range(query_params):
    """``(start, end)`` of ``?start=&end=``; 400 when missing, reversed or
    wider than :data:`MAX_RANGE_DAYS`."""
    start = parse_moment(query_params.get('start'))
    end = parse_moment(query_params.get('end'))
    if start is None or end is None:
        raise ValidationError({'detail': _('start and end (ISO dates) are required')})
    if end <= start or end - start > datetime.timedelta(days=MAX_RANGE_DAYS):
        raise ValidationError({'detail': _('the range must go forward and span at '
                                           'most %d days') % MAX_RANGE_DAYS})
    return start, end


def bound(build, name, moment):
    """``moment`` as column ``name`` compares: a date for a date column."""
    if build.kinds.get(name) == 'date':
        return timezone.localtime(moment).date()
    return moment


def range_q(build, start, end):
    """The rows whose event overlaps ``[start, end)``: it starts before the
    end and ends after the start (or, without an end, starts in the range)."""
    first, last = build.start_field, build.end_field
    q = Q(**{first + '__lt': bound(build, first, end)})
    starts_in = Q(**{first + '__gte': bound(build, first, start)})
    if last:
        q &= Q(**{last + '__gte': bound(build, last, start)}) | (
            Q(**{last + '__isnull': True}) & starts_in)
    else:
        q &= starts_in
    return q


def iso(build, name, value, end=False):
    """``(text, all day)`` of a start or end value for FullCalendar."""
    if isinstance(value, datetime.datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.isoformat(), False
    if isinstance(value, datetime.date):
        # FullCalendar's end of an all-day event is exclusive.
        return (value + datetime.timedelta(days=1) if end else value).isoformat(), True
    return None, False


def rule_colors(build, source, request, queryset, pks):
    """``{pk: colour}`` of the ``color_rules``: the first rule that matches;
    one query per rule."""
    result = {}
    if not build.color_rules or not pks:
        return result
    colmap = source.column_map(request)
    for rule in build.color_rules:
        try:
            q = query.filter_q(source, request, rule['filter'], colmap, queryset.model)
        except DjangoValidationError:
            continue
        for pk in queryset.filter(pk__in=pks).filter(q).values_list('pk', flat=True):
            result.setdefault(pk, rule['color'])
    return result


def events_in_range(build, source, request, queryset, start, end, hidden=()):
    """``([FullCalendar event], truncated)`` of the rows in ``[start, end)``:
    one query for the rows, at most ``build.limit``, plus those of the
    relations shown and one per colour rule."""
    queryset = queryset.filter(range_q(build, start, end)).order_by(
        build.start_field, 'pk')
    rows = read_rows(build, source, request, queryset[:build.limit + 1])
    truncated = len(rows) > build.limit
    rows = rows[:build.limit]
    colors = rule_colors(build, source, request, queryset,
                         [row['pk'] for row in rows])
    links = link_urls(build, request)
    events = []
    for row in rows:
        begin, all_day = iso(build, build.start_field, row.get(build.start_field))
        if begin is None:
            continue
        texts = row_texts(build, row, hidden)
        event = {'id': str(row['pk']), 'title': texts['title'], 'start': begin,
                 'allDay': all_day,
                 'extendedProps': {'subtitle': texts['subtitle'],
                                   'fields': texts['fields']}}
        if build.end_field and row.get(build.end_field) is not None:
            event['end'] = iso(build, build.end_field, row[build.end_field],
                               end=True)[0]
        color = colors.get(row['pk'])
        if color is None and build.color_field:
            value = row.get(build.color_field)
            color = build.colors.get(str(value), value if not build.colors else None)
        if color and COLOR.match(str(color)):
            event['color'] = str(color)
        row_link = row_links(links, row['pk'])
        if row_link:
            event['url'] = row_link[0]['url']
        events.append(event)
    return events, truncated


# -- map -----------------------------------------------------------------------------

def parse_bbox(text):
    """``(west, south, east, north)`` of ``?bbox=``, or None; 400 if wrong."""
    if not text:
        return None
    try:
        west, south, east, north = (float(part) for part in str(text).split(','))
    except ValueError:
        raise ValidationError({'detail': _('bbox is west,south,east,north')}) from None
    if not (-90 <= south <= north <= 90):
        raise ValidationError({'detail': _('bbox is west,south,east,north')})
    # A map scrolled past the antimeridian sends longitudes beyond 180.
    if east - west >= 360:
        west, east = -180.0, 180.0
    else:
        west = ((west + 180) % 360) - 180
        east = ((east + 180) % 360) - 180
    return west, south, east, north


def point_coordinates(name):
    """``(lat, lng)`` expressions of a ``"lat,lng"`` text column, ``NULL``
    for a value that is not one (the CASE keeps the cast from failing on
    PostgreSQL)."""
    column = models.F(name)
    comma = StrIndex(column, Value(','))
    valid = Q(**{name + '__regex': POINT_RE})
    lat = Cast(Trim(Left(column, comma - 1)), FloatField())
    lng = Cast(Trim(Substr(column, comma + 1)), FloatField())
    return (Case(When(valid, then=lat), default=None, output_field=FloatField()),
            Case(When(valid, then=lng), default=None, output_field=FloatField()))


def map_points(build, source, request, queryset, bbox=None, hidden=()):
    """``([point], truncated)``: the rows with a point (inside ``bbox``),
    at most ``build.limit``, in one query plus those of the relations shown.
    The popup is HTML rendered here, escaped."""
    name = build.point_field
    queryset = queryset.filter(**{name + '__regex': POINT_RE})
    if bbox is not None:
        west, south, east, north = bbox
        lat, lng = point_coordinates(name)
        queryset = queryset.annotate(gtdesign_lat=lat, gtdesign_lng=lng).filter(
            gtdesign_lat__gte=south, gtdesign_lat__lte=north)
        if west <= east:
            queryset = queryset.filter(gtdesign_lng__gte=west, gtdesign_lng__lte=east)
        else:
            queryset = queryset.filter(Q(gtdesign_lng__gte=west)
                                       | Q(gtdesign_lng__lte=east))
    rows = read_rows(build, source, request, queryset[:build.limit + 1])
    truncated = len(rows) > build.limit
    links = link_urls(build, request)
    points = []
    for row in rows[:build.limit]:
        found = parse_point(row.get(name))
        if found is None:
            continue
        texts = row_texts(build, row, hidden)
        point_links = row_links(links, row['pk'])
        points.append({
            'lat': found[0], 'lng': found[1], 'title': texts['title'],
            'popup': render_to_string('gtdesigns/components/map_popup.html', {
                'texts': texts, 'links': point_links}),
        })
    return points, truncated


# -- the three components ------------------------------------------------------------

class CardsComponent(RegionComponent):
    """The rows as cards: title, subtitle, image, fields and row links, with
    paging, search and facets."""

    type = 'cards'
    label = gettext_lazy('Cards')
    icon = 'fa fa-th-large'
    build_class = CardsBuild
    template = 'gtdesigns/components/cards.html'
    viewset = CardsViewSet
    roles = {'image_field': (('string', 'text'), False)}
    default_props = {'page_size': CARDS_PAGE_SIZE, 'per_row': 3}
    props_schema = {
        'type': 'object',
        'required': ['title_field'],
        'additionalProperties': False,
        'properties': {
            **common_properties(),
            'image_field': column_prop('Image of each card (a file field or a URL)',
                                       'image'),
            'page_size': {'type': 'integer', 'minimum': 1,
                          'maximum': CARDS_MAX_PAGE_SIZE,
                          'title': 'Cards per page (default %d)' % CARDS_PAGE_SIZE},
            'per_row': {'enum': [1, 2, 3, 4, 6],
                        'title': 'Cards per row on a wide screen'},
            'search': {'type': 'boolean', 'default': True,
                       'title': 'Show a search box'},
        },
    }

    def resolve_more(self, build, props, rctx, path, columns):
        build.page_size = props.get('page_size', CARDS_PAGE_SIZE)
        build.per_row = props.get('per_row', 3)
        build.search = props.get('search', True)

    def config(self, build, rctx):
        return {'page_size': build.page_size, 'search': build.search}


class CalendarComponent(RegionComponent):
    """The rows as events of FullCalendar: from a date or date-time column
    to another (optional), coloured by a column or by rules, each one opening
    its row link. Only the visible range is read."""

    type = 'calendar'
    label = gettext_lazy('Calendar')
    icon = 'fa fa-calendar'
    build_class = CalendarBuild
    template = 'gtdesigns/components/calendar.html'
    viewset = CalendarViewSet
    roles = {'start_field': (DATE_KINDS, True), 'end_field': (DATE_KINDS, False),
             'color_field': (('string', 'choices', 'text'), False)}
    default_props = {'initial_view': 'dayGridMonth'}
    props_schema = {
        'type': 'object',
        'required': ['title_field', 'start_field'],
        'additionalProperties': False,
        'properties': {
            **common_properties(),
            'start_field': column_prop('Start (a date or date-time)', 'date'),
            'end_field': column_prop('End (optional)', 'date'),
            'color_field': column_prop('Colour of each event (a colour, or a '
                                       'value of "colors")'),
            'colors': {'type': 'object', 'additionalProperties': COLOR_SCHEMA,
                       'x-widget': 'value-colors',
                       'title': 'Colour by value of the colour field'},
            'color_rules': {
                'type': 'array', 'x-widget': 'color-rules',
                'title': 'Colour rules: the first whose filter matches',
                'items': {'type': 'object', 'required': ['filter', 'color'],
                          'additionalProperties': False,
                          'properties': {'filter': {'type': 'object',
                                                    'x-widget': 'filter'},
                                         'color': COLOR_SCHEMA}}},
            'initial_view': {'enum': list(CALENDAR_VIEWS), 'title': 'First view'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': CALENDAR_MAX_LIMIT,
                      'title': 'At most this many events per range (default %d)'
                               % CALENDAR_LIMIT},
        },
    }

    def resolve_more(self, build, props, rctx, path, columns):
        build.colors = dict(props.get('colors') or {})
        if build.colors and not build.color_field:
            rctx.error(path + '.props.colors', _('colors needs a color_field'))
        rules = props.get('color_rules') or []
        for index, rule in enumerate(rules):
            column = columns.get((rule.get('filter') or {}).get('column'))
            if column is None or not column.filterable:
                rctx.error('%s.props.color_rules[%d].filter' % (path, index),
                           _('unknown column %r') % (
                               (rule.get('filter') or {}).get('column'),))
        build.color_rules = [dict(rule) for rule in rules]
        build.initial_view = props.get('initial_view', 'dayGridMonth')
        build.limit = props.get('limit', CALENDAR_LIMIT)

    def config(self, build, rctx):
        locale = calendar_locale(rctx.request)
        config = {'initial_view': build.initial_view, 'limit': build.limit,
                  'fullcalendar': static(FULLCALENDAR), 'locale': locale}
        if locale and locale.split('-')[0] != 'en':
            # Only a page in another language loads the locales.
            config['locales'] = static(FULLCALENDAR_LOCALES)
        return config


def calendar_locale(request):
    """The FullCalendar locale of the page: the language of ``request``
    (``LANGUAGE_CODE``, set by ``LocaleMiddleware``) or the active one, in
    lower case (``es``, ``pt-br``). FullCalendar falls back from ``pt-br`` to
    ``pt``, and to English for a language it does not know."""
    code = getattr(request, 'LANGUAGE_CODE', '') or translation.get_language() or ''
    return code.lower()


class MapComponent(RegionComponent):
    """The rows as points of a Leaflet map (``maplib.js``): from a
    ``GTPointField`` column, with a popup of their fields and an optional
    clustering; at most ``limit`` points, of the visible box."""

    type = 'map'
    label = gettext_lazy('Map')
    icon = 'fa fa-map-marker'
    build_class = MapBuild
    template = 'gtdesigns/components/map.html'
    viewset = MapViewSet
    roles = {'point_field': (('string',), True)}
    default_props = {'cluster': True}
    props_schema = {
        'type': 'object',
        'required': ['point_field'],
        'additionalProperties': False,
        'properties': {
            **common_properties(),
            'point_field': column_prop('Point ("lat,lng", a GTPointField)', 'point'),
            'cluster': {'type': 'boolean', 'default': False,
                        'title': 'Group near points (clustering)'},
            'bbox': {'type': 'boolean', 'default': True,
                     'title': 'Load the points of the visible area when the map '
                              'moves'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': MAP_MAX_LIMIT,
                      'title': 'At most this many points (default %d)' % MAP_LIMIT},
            'center': {'type': 'array', 'items': {'type': 'number'},
                       'minItems': 2, 'maxItems': 2,
                       'title': 'Centre [lat, lng] (default: fit the points)'},
            'zoom': {'type': 'integer', 'minimum': 1, 'maximum': 19,
                     'title': 'Zoom (with a centre)'},
            'height': {'type': 'integer', 'minimum': 150, 'maximum': 2000,
                       'title': 'Height in pixels (default 420)'},
        },
    }

    def resolve_more(self, build, props, rctx, path, columns):
        name = build.point_field
        model_field = model_field_of(build.model, name) if name else None
        if name and build.model is not None and model_field is not None and \
                not isinstance(model_field, GTPointField):
            rctx.error(path + '.props.point_field',
                       _('%r is not a GTPointField ("lat,lng")') % (name,))
        build.cluster = props.get('cluster', False)
        build.bbox = props.get('bbox', True)
        build.limit = props.get('limit', MAP_LIMIT)
        build.center = props.get('center')
        build.zoom = props.get('zoom')
        build.height = props.get('height', 420)

    def config(self, build, rctx):
        config = {'cluster': build.cluster, 'bbox': build.bbox, 'limit': build.limit}
        if build.cluster:
            config['markercluster'] = [static(path) for path in MARKERCLUSTER]
        if build.center:
            config['center'] = build.center
            config['zoom'] = build.zoom or 13
        return config


REGION_COMPONENTS = [CardsComponent, CalendarComponent, MapComponent]
