"""More region components: the rows of a data source as a tree, as a
timeline, and metric cards with a comparison against the previous period
(``tree``, ``timeline`` and ``metrics``; C17).

They are region components (:mod:`djgentelella.designs.regions`, C15) and
take what those take: ``datasource`` (or an exposed ``model`` with
``site_field``), the role columns, ``fields``, ``row_links``,
``column_conditions``, ``filtered_by`` and ``perms``. They read only
``get_queryset(request)`` of the data source, through
:func:`~djgentelella.datasources.query.apply_params`, so the facets of the
page filter them, and their endpoints answer 403 without the permissions of
the build or of the data source (and 503 when the source is unavailable:
``DataSourceUnavailable``).

``tree``
    ``parent_field`` names the parent of each row (a foreign key to the same
    model, or a column holding the ``id_field`` of the parent; ``id_field``
    is the primary key when empty), ``icon_field`` an optional CSS class.
    ``load: "lazy"`` (the default) asks for one level at a time --
    ``?parent=<id>&offset=`` -- at most ``limit`` rows per request;
    ``"full"`` reads at most ``limit`` rows at once, in pre-order. A row whose
    parent is not among the rows (absent, filtered out, beyond the limit) is
    shown at the root marked ``orphan``; the rows of a cycle, unreachable
    from any root, show one of them at the root marked ``cycle``. Neither
    hangs the page: nothing is walked recursively and the browser never opens
    a node that is already one of its ancestors.

``timeline``
    ``start_field`` (and an optional ``end_field``), ``title_field``,
    ``subtitle_field``, ``description_field`` and a colour per value
    (``color_field`` + ``colors``, or ``color_rules``) like the calendar's.
    Newest first, ``page_size`` items per request, paging backwards with a
    keyset cursor (``?cursor=``): the same queries for the first page and the
    hundredth. ``?from=&to=`` limit the range.

``metrics``
    One or more KPI cards (``metrics``), each an aggregate of C4 (``count``,
    ``count_distinct``, ``sum``, ``avg``, ``min``, ``max``) over a column,
    with optional filters (C4) and a format (``number``, ``currency``,
    ``percent``). With ``date_field`` and ``period`` (``day``, ``week``,
    ``month``, ``quarter``, ``year``) a card shows the current period and,
    with ``compare``, the change against the previous one: absolute and in
    percent (none when the previous one is empty or zero), with an arrow
    coloured by ``higher_is_better``. Every card is computed in a single
    query.
"""

import base64
import binascii
import datetime
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Avg, Count, F, Max, Min, Q, Sum
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django.utils import formats, timezone
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from rest_framework import viewsets
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.response import Response

from djgentelella.authorization import evaluate_condition, validate_condition
from djgentelella.datasources import query
from djgentelella.designs.data_components import (
    can, endpoint_url, json_config, no_permission,
)
from djgentelella.designs.regions import (
    COLOR, COLOR_SCHEMA, DATE_KINDS, RegionBuild, RegionComponent, RegionMixin,
    column_prop, common_properties, display, iso, link_urls, model_field_of,
    parse_moment, read_rows, region_source, row_links, row_texts, rule_colors,
)

__all__ = ['METRIC_FORMATS', 'METRIC_FUNCTIONS', 'MetricsBuild',
           'MetricsComponent', 'MetricsViewSet', 'PERIOD_LABELS',
           'TREE_TIMELINE_METRICS_COMPONENTS', 'TimelineBuild',
           'TimelineComponent', 'TimelineViewSet', 'TreeBuild', 'TreeComponent',
           'TreeViewSet', 'format_metric', 'metric_values', 'period_bounds',
           'timeline_page', 'tree_cycles', 'tree_full', 'tree_level']

SCRIPT = 'gentelella/js/designs/tree_timeline_metrics.js'
STYLE = 'gentelella/css/tree_timeline_metrics.css'
#: A CSS class an icon column may give (``fa fa-folder``); anything else is
#: dropped.
ICON = re.compile(r'^[\w -]{1,80}$')
#: Rows per request of a tree: per level (lazy) or in all (full).
TREE_LIMIT, TREE_MAX_LIMIT = 200, 5000
#: How many ``(id, parent)`` pairs a lazy tree reads to find its cycles; a
#: larger source is not checked (the answer says so).
TREE_SCAN_LIMIT = 20000
TREE_LOADS = ('lazy', 'full')
TIMELINE_PAGE_SIZE, TIMELINE_MAX_PAGE_SIZE = 20, 100
#: The aggregates a metric card computes, as Django aggregates.
METRIC_FUNCTIONS = {
    'count': lambda name, q: Count(name, filter=q),
    'count_distinct': lambda name, q: Count(name, distinct=True, filter=q),
    'sum': lambda name, q: Sum(name, filter=q),
    'avg': lambda name, q: Avg(name, filter=q),
    'min': lambda name, q: Min(name, filter=q),
    'max': lambda name, q: Max(name, filter=q),
}
METRIC_FORMATS = ('number', 'currency', 'percent')
MAX_METRICS = 12
PERIOD_LABELS = {
    'day': (gettext_lazy('Today'), gettext_lazy('vs. the previous day')),
    'week': (gettext_lazy('This week'), gettext_lazy('vs. the previous week')),
    'month': (gettext_lazy('This month'), gettext_lazy('vs. the previous month')),
    'quarter': (gettext_lazy('This quarter'),
                gettext_lazy('vs. the previous quarter')),
    'year': (gettext_lazy('This year'), gettext_lazy('vs. the previous year')),
}


def clean_icon(value):
    value = str(value or '').strip()
    return value if ICON.match(value) else ''


def config_with_source(component, build, rctx, url):
    """What :meth:`RegionComponent.render` puts in the configuration of the
    browser: the endpoint, and with a data source its state for facets."""
    config = {'id': build.id, 'type': build.type, 'url': url}
    if build.datasource:
        try:
            config['datasource_url'] = reverse('gtdatasource',
                                               kwargs={'name': build.datasource})
            config['group'] = build.group or 'gtdesign:%s' % build.id
        except NoReverseMatch:
            pass
    config.update(component.config(build, rctx))
    return config


def int_param(query_params, name, default=0, maximum=None):
    text = query_params.get(name)
    if text in (None, ''):
        return default
    try:
        value = int(text)
    except (TypeError, ValueError):
        raise ValidationError({'detail': _('%s must be a whole number') % name}) \
            from None
    if value < 0 or (maximum is not None and value > maximum):
        raise ValidationError({'detail': _('%s is out of range') % name})
    return value


def raw_value(value):
    """The value of a relation as ``serialize_rows`` gives it: its id."""
    if isinstance(value, dict):
        return value.get('id')
    return value


def key_of(value):
    """The text a tree compares ids and parents by; ``None`` for no parent."""
    value = raw_value(value)
    if value is None or value == '':
        return None
    return str(value)


# -- tree ----------------------------------------------------------------------------

@dataclass
class TreeBuild(RegionBuild):
    #: The column of the id the parents name; '' is the primary key.
    id_field: str = ''
    parent_field: str = ''
    #: A column holding a CSS class (``fa fa-folder``).
    icon_field: str = ''
    load: str = 'lazy'
    limit: int = TREE_LIMIT
    #: Full load: levels open at first (0: only the roots shown).
    expand: int = 1

    @property
    def id_name(self):
        return self.id_field or 'pk'

    def read_columns(self):
        names = super().read_columns()
        for name in (self.id_field, self.parent_field, self.icon_field):
            if name and name not in names:
                names.append(name)
        return names


def tree_node(build, row, links, hidden, **extra):
    texts = row_texts(build, row, hidden)
    node_links = row_links(links, row['pk'])
    node = {'key': key_of(row.get(build.id_field) if build.id_field else row['pk']),
            'title': texts['title'], 'subtitle': texts['subtitle'],
            'fields': texts['fields'], 'links': node_links,
            'url': node_links[0]['url'] if node_links else '',
            'icon': clean_icon(row.get(build.icon_field)) if build.icon_field
            and build.icon_field not in hidden else ''}
    node.update(extra)
    return node


def tree_cycles(pairs):
    """The ids that stand for the cycles among ``pairs`` (``[(id, parent)]``,
    as :func:`key_of` texts): rows no root reaches. One id per cycle, the
    smallest of the cycle; walked with loops and sets, never recursively."""
    parent_of = {}
    for key, parent in pairs:
        if key is not None:
            parent_of[key] = parent
    children = defaultdict(list)
    roots = []
    for key, parent in parent_of.items():
        if parent is None or parent not in parent_of:
            roots.append(key)
        else:
            children[parent].append(key)
    reached = set()

    def reach(starts):
        stack = list(starts)
        while stack:
            key = stack.pop()
            if key in reached:
                continue
            reached.add(key)
            stack.extend(children.get(key, ()))

    reach(roots)
    found = []
    for key in sorted(parent_of, key=sort_key):
        if key in reached:
            continue
        # Up the parents until one repeats: that one is on the cycle.
        path, seen = [], set()
        while key not in seen:
            seen.add(key)
            path.append(key)
            key = parent_of[key]
        cycle = path[path.index(key):]
        first = min(cycle, key=sort_key)
        found.append(first)
        reach([first])
    return found


def sort_key(text):
    """Numbers by value, then texts: the order a cycle is told by."""
    return (0, int(text), '') if text.lstrip('-').isdigit() else (1, 0, text)


def tree_level(build, source, request, queryset, parent=None, offset=0,
               hidden=()):
    """One level of a lazy tree: ``{'nodes', 'next_offset', 'orphans',
    'cycles', 'checked'}``. The roots (``parent`` None) are the rows without
    a parent, those whose parent is not among the rows (``orphan``) and, on
    the first page, one row of each cycle (``cycle``). A constant number of
    queries: the level, its rows, which of them have children and, for the
    roots, the ``(id, parent)`` pairs to find the cycles in."""
    id_name, parent_name = build.id_name, build.parent_field
    queryset = queryset.exclude(**{id_name + '__isnull': True})
    result = {'nodes': [], 'next_offset': None, 'orphans': 0, 'cycles': 0,
              'checked': True}
    cycle_keys = []
    try:
        if parent is None:
            present = queryset.order_by().values(id_name)
            no_parent = Q(**{parent_name + '__isnull': True})
            if build.kinds.get(parent_name) in ('string', 'text'):
                no_parent |= Q(**{parent_name: ''})
            level = queryset.filter(no_parent | ~Q(**{parent_name + '__in': present}))
            if offset == 0:
                pairs = list(queryset.order_by().values_list(
                    id_name, parent_name)[:TREE_SCAN_LIMIT + 1])
                if len(pairs) > TREE_SCAN_LIMIT:
                    result['checked'] = False
                else:
                    cycle_keys = tree_cycles([(key_of(a), key_of(b))
                                              for a, b in pairs])
        else:
            level = queryset.filter(**{parent_name: parent}).exclude(
                **{id_name: parent})
        page = list(level.values_list('pk', flat=True)[offset:offset + build.limit + 1])
    except (ValueError, TypeError, DjangoValidationError):
        raise ValidationError({'detail': _('parent is not an id of this tree')}) \
            from None
    if len(page) > build.limit:
        page = page[:build.limit]
        result['next_offset'] = offset + build.limit
    rows = {row['pk']: row for row in read_rows(
        build, source, request, queryset.filter(pk__in=page))}
    ordered = [rows[pk] for pk in page if pk in rows]
    cycle_rows = []
    if cycle_keys:
        by_key = {}
        for row in read_rows(build, source, request,
                             queryset.filter(**{id_name + '__in': cycle_keys})):
            by_key[key_of(row.get(build.id_field) if build.id_field
                          else row['pk'])] = row
        cycle_rows = [by_key[key] for key in cycle_keys if key in by_key]
    keys = [key_of(row.get(build.id_field) if build.id_field else row['pk'])
            for row in ordered + cycle_rows]
    with_children = set()
    if keys:
        try:
            with_children = {key_of(value) for value in queryset.order_by().filter(
                **{parent_name + '__in': keys}).exclude(
                **{id_name: F(parent_name)}).values_list(
                parent_name, flat=True).distinct()}
        except (ValueError, TypeError, DjangoValidationError):
            with_children = set()
    links = link_urls(build, request)
    for row in ordered:
        orphan = parent is None and key_of(row.get(parent_name)) is not None
        node = tree_node(build, row, links, hidden, orphan=orphan, cycle=False)
        node['children'] = node['key'] in with_children
        result['orphans'] += orphan
        result['nodes'].append(node)
    for row in cycle_rows:
        node = tree_node(build, row, links, hidden, orphan=False, cycle=True)
        node['children'] = node['key'] in with_children
        result['nodes'].append(node)
    result['cycles'] = len(cycle_rows)
    return result


def tree_full(build, source, request, queryset, hidden=()):
    """A whole tree, at most ``build.limit`` rows, in pre-order: ``{'nodes':
    [{..., 'parent', 'depth'}], 'truncated', 'orphans', 'cycles'}``. Every
    row appears once; one query for the rows (plus those of the relations
    shown)."""
    rows = read_rows(build, source, request, queryset[:build.limit + 1])
    truncated = len(rows) > build.limit
    rows = rows[:build.limit]
    by_key, order = {}, []
    for row in rows:
        key = key_of(row.get(build.id_field) if build.id_field else row['pk'])
        if key is not None and key not in by_key:
            by_key[key] = row
            order.append(key)
    parent_of = {key: key_of(by_key[key].get(build.parent_field)) for key in order}
    children = defaultdict(list)
    roots, orphans = [], set()
    for key in order:
        parent = parent_of[key]
        if parent is None or parent not in by_key:
            roots.append(key)
            if parent is not None:
                orphans.add(key)
        else:
            children[parent].append(key)
    cycles = tree_cycles([(key, parent_of[key]) for key in order])
    links = link_urls(build, request)
    nodes, placed = [], set()
    stack = [(key, None, 0) for key in reversed(roots + cycles)]
    while stack:
        key, parent, depth = stack.pop()
        if key in placed:
            continue
        placed.add(key)
        node = tree_node(build, by_key[key], links, hidden, parent=parent,
                         depth=depth, orphan=key in orphans,
                         cycle=parent is None and key in cycles)
        kids = [kid for kid in children.get(key, ()) if kid not in placed]
        node['children'] = bool(kids)
        nodes.append(node)
        stack.extend((kid, key, depth + 1) for kid in reversed(kids))
    return {'nodes': nodes, 'truncated': truncated, 'orphans': len(orphans),
            'cycles': len(cycles)}


class TreeViewSet(RegionMixin, viewsets.ViewSet):
    """A ``tree`` node: one level (``?parent=&offset=``) or, with ``load:
    "full"``, the whole tree."""

    def list(self, request, *args, **kwargs):
        build = self.build
        queryset = self.rows_queryset()
        if build.load == 'full':
            return Response(tree_full(build, self.source, request, queryset,
                                      self.hidden))
        parent = request.query_params.get('parent')
        if parent == '':
            parent = None
        offset = int_param(request.query_params, 'offset')
        return Response(tree_level(build, self.source, request, queryset, parent,
                                   offset, self.hidden))


class TreeComponent(RegionComponent):
    """The rows as a tree: each row under its parent, opened one level at a
    time or read at once, with row links and facets."""

    type = 'tree'
    label = gettext_lazy('Tree')
    icon = 'fa fa-sitemap'
    build_class = TreeBuild
    template = 'gtdesigns/components/tree.html'
    viewset = TreeViewSet
    roles = {'id_field': (('integer', 'string'), False),
             'parent_field': (('fk', 'integer', 'string'), True),
             'icon_field': (('string', 'choices', 'text'), False)}
    default_props = {'load': 'lazy'}
    props_schema = {
        'type': 'object',
        'required': ['title_field', 'parent_field'],
        'additionalProperties': False,
        'properties': {
            **common_properties(),
            'id_field': column_prop('Id the parents name (empty: the primary key)',
                                    'id'),
            'parent_field': column_prop('Parent of each row (a foreign key to the '
                                        'same model, or a column with the id)',
                                        'parent'),
            'icon_field': column_prop('Icon of each row (a CSS class)', 'icon'),
            'load': {'enum': list(TREE_LOADS), 'default': 'lazy',
                     'title': 'Load one level at a time (lazy) or all at once '
                              '(full)'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': TREE_MAX_LIMIT,
                      'title': 'At most this many rows per level (lazy) or in all '
                               '(full) (default %d)' % TREE_LIMIT},
            'expand': {'type': 'integer', 'minimum': 0, 'maximum': 20,
                       'title': 'Levels open at first (full load; default 1)'},
        },
    }

    def resolve_more(self, build, props, rctx, path, columns):
        build.load = props.get('load', 'lazy')
        build.limit = props.get('limit', TREE_LIMIT)
        build.expand = props.get('expand', 1)
        parent = build.parent_field
        if not parent:
            return
        where = path + '.props.parent_field'
        kind = build.kinds.get(parent)
        id_kind = build.kinds.get(build.id_field) if build.id_field else None
        if kind == 'fk':
            if build.id_field and build.model is not None and \
                    build.id_field != build.model._meta.pk.name:
                rctx.error(path + '.props.id_field',
                           _('a foreign key parent names the primary key: leave '
                             'id_field empty'))
            target = self.related_model(build, parent)
            if build.model is not None and target is not None and \
                    target is not build.model:
                rctx.error(where, _('%(field)r is not a foreign key to %(model)s')
                           % {'field': parent, 'model': build.model._meta.label})
        elif build.id_field and id_kind != kind:
            rctx.error(where, _('the parent (%(parent)s) and the id (%(id)s) are '
                                'not of the same kind') % {'parent': kind,
                                                           'id': id_kind})

    @staticmethod
    def related_model(build, name):
        return getattr(model_field_of(build.model, name), 'related_model', None)

    def config(self, build, rctx):
        return {'load': build.load, 'limit': build.limit, 'expand': build.expand}

    def sample(self, build):
        rows = super().sample(build)
        for index, row in enumerate(rows):
            row['depth'] = index
        return rows

    def media(self, build, rctx):
        return {'js': [SCRIPT], 'css': [STYLE]}


# -- timeline ------------------------------------------------------------------------

@dataclass
class TimelineBuild(RegionBuild):
    start_field: str = ''
    end_field: str = ''
    description_field: str = ''
    color_field: str = ''
    colors: dict = field(default_factory=dict)
    color_rules: list = field(default_factory=list)
    page_size: int = TIMELINE_PAGE_SIZE

    def read_columns(self):
        names = super().read_columns()
        for name in (self.start_field, self.end_field, self.description_field,
                     self.color_field):
            if name and name not in names:
                names.append(name)
        return names


def encode_cursor(value, pk):
    if isinstance(value, (datetime.datetime, datetime.date)):
        value = value.isoformat()
    text = json.dumps([value, pk], default=str)
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip('=')


def decode_cursor(build, text):
    """``(start, pk)`` of a cursor; 400 if it is not one."""
    try:
        padded = text + '=' * (-len(text) % 4)
        value, pk = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except (ValueError, TypeError, binascii.Error, UnicodeDecodeError):
        raise ValidationError({'detail': _('invalid cursor')}) from None
    moment = parse_moment(value)
    if moment is None or not isinstance(pk, (int, str)):
        raise ValidationError({'detail': _('invalid cursor')})
    if build.kinds.get(build.start_field) == 'date':
        moment = datetime.date.fromisoformat(str(value)[:10])
    return moment, pk


def bound_of(build, moment):
    if build.kinds.get(build.start_field) == 'date':
        return timezone.localtime(moment).date()
    return moment


def timeline_page(build, source, request, queryset, cursor=None, start=None,
                  end=None, hidden=()):
    """``{'items', 'next'}``: at most ``build.page_size`` rows, newest first,
    older than ``cursor`` (``(start, pk)`` of the last row shown) and starting
    in ``[start, end)``. ``next`` is the cursor of the following page, or
    ``None``. One query for the rows (plus those of the relations shown and
    one per colour rule), whatever page it is."""
    name = build.start_field
    queryset = queryset.exclude(**{name + '__isnull': True})
    if start is not None:
        queryset = queryset.filter(**{name + '__gte': bound_of(build, start)})
    if end is not None:
        queryset = queryset.filter(**{name + '__lt': bound_of(build, end)})
    if cursor is not None:
        moment, pk = cursor
        try:
            queryset = queryset.filter(Q(**{name + '__lt': moment})
                                       | Q(**{name: moment, 'pk__lt': pk}))
        except (ValueError, TypeError, DjangoValidationError):
            raise ValidationError({'detail': _('invalid cursor')}) from None
    queryset = queryset.order_by('-' + name, '-pk')
    rows = read_rows(build, source, request, queryset[:build.page_size + 1])
    more = len(rows) > build.page_size
    rows = rows[:build.page_size]
    colors = rule_colors(build, source, request, queryset, [row['pk'] for row in rows])
    links = link_urls(build, request)
    items = []
    for row in rows:
        moment = row.get(name)
        begin, all_day = iso(build, name, moment)
        texts = row_texts(build, row, hidden)
        item_links = row_links(links, row['pk'])
        item = {'id': str(row['pk']), 'title': texts['title'],
                'subtitle': texts['subtitle'], 'fields': texts['fields'],
                'start': begin, 'all_day': all_day,
                'when': display(build, name, moment),
                'group': group_label(moment), 'links': item_links,
                'url': item_links[0]['url'] if item_links else '',
                'description': ''}
        if build.description_field and build.description_field not in hidden:
            item['description'] = display(build, build.description_field,
                                          row.get(build.description_field))
        if build.end_field and row.get(build.end_field) is not None:
            item['end'] = iso(build, build.end_field, row[build.end_field])[0]
            item['until'] = display(build, build.end_field, row[build.end_field])
        color = colors.get(row['pk'])
        if color is None and build.color_field:
            value = row.get(build.color_field)
            color = build.colors.get(str(value), value if not build.colors else None)
        if color and COLOR.match(str(color)):
            item['color'] = str(color)
        items.append(item)
    following = None
    if more and rows:
        following = encode_cursor(rows[-1].get(name), rows[-1]['pk'])
    return {'items': items, 'next': following}


def group_label(moment):
    """The month an item is listed under (``November 2026``)."""
    if isinstance(moment, datetime.datetime) and timezone.is_aware(moment):
        moment = timezone.localtime(moment)
    if isinstance(moment, datetime.date):
        return formats.date_format(moment, 'YEAR_MONTH_FORMAT')
    return ''


class TimelineViewSet(RegionMixin, viewsets.ViewSet):
    """A page of a ``timeline`` node: ``?cursor=&from=&to=&params=``."""

    def list(self, request, *args, **kwargs):
        params = request.query_params
        start, end = (self.moment(params, name) for name in ('from', 'to'))
        cursor = params.get('cursor')
        return Response(timeline_page(
            self.build, self.source, request, self.rows_queryset(),
            decode_cursor(self.build, cursor) if cursor else None, start, end,
            self.hidden))

    @staticmethod
    def moment(params, name):
        text = params.get(name)
        if not text:
            return None
        moment = parse_moment(text)
        if moment is None:
            raise ValidationError({'detail': _('%s is not an ISO date') % name})
        return moment


class TimelineComponent(RegionComponent):
    """The rows on a vertical timeline, newest first: date, title,
    description, a colour per value and the row link, paging backwards."""

    type = 'timeline'
    label = gettext_lazy('Timeline')
    icon = 'fa fa-history'
    build_class = TimelineBuild
    template = 'gtdesigns/components/timeline.html'
    viewset = TimelineViewSet
    roles = {'start_field': (DATE_KINDS, True), 'end_field': (DATE_KINDS, False),
             'description_field': (('string', 'text', 'choices'), False),
             'color_field': (('string', 'choices', 'text'), False)}
    default_props = {'page_size': TIMELINE_PAGE_SIZE}
    props_schema = {
        'type': 'object',
        'required': ['title_field', 'start_field'],
        'additionalProperties': False,
        'properties': {
            **common_properties(),
            'start_field': column_prop('Date of each item (a date or date-time)',
                                       'date'),
            'end_field': column_prop('End (optional)', 'date'),
            'description_field': column_prop('Description of each item', 'text'),
            'color_field': column_prop('Colour of each item (a colour, or a value '
                                       'of "colors")', 'color'),
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
            'page_size': {'type': 'integer', 'minimum': 1,
                          'maximum': TIMELINE_MAX_PAGE_SIZE,
                          'title': 'Items per page (default %d)' % TIMELINE_PAGE_SIZE},
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
        build.page_size = props.get('page_size', TIMELINE_PAGE_SIZE)

    def config(self, build, rctx):
        return {'page_size': build.page_size}

    def media(self, build, rctx):
        return {'js': [SCRIPT], 'css': [STYLE]}


# -- metrics -------------------------------------------------------------------------

@dataclass
class MetricsBuild(RegionBuild):
    #: ``[{'key', 'label', 'fn', 'column', 'filters', 'format', 'decimals',
    #: 'prefix', 'suffix', 'icon', 'compare', 'higher_is_better',
    #: 'condition'}]``, normalized.
    metrics: list = field(default_factory=list)
    #: The date or date-time column of the periods ('' for none).
    date_field: str = ''
    period: str = 'month'
    #: Compare with the same stretch of the previous period (the first 10
    #: days of last month on the 10th) instead of the whole of it.
    to_date: bool = False
    #: Cards per row on a wide screen.
    per_row: int = 4


METRIC_SCHEMA = {
    'type': 'object',
    'required': ['label', 'fn'],
    'additionalProperties': False,
    'properties': {
        'label': {'type': 'string', 'minLength': 1, 'title': 'Label'},
        'fn': {'enum': list(METRIC_FUNCTIONS), 'title': 'Aggregate'},
        'column': {'type': 'string', 'x-widget': 'model-field',
                   'x-filter': 'numeric',
                   'title': 'Column (every function but count)'},
        'filters': {'type': 'array', 'title': 'Only the rows matching',
                    'items': {'type': 'object', 'x-widget': 'filter'}},
        'format': {'enum': list(METRIC_FORMATS), 'default': 'number',
                   'title': 'Format'},
        'decimals': {'type': 'integer', 'minimum': 0, 'maximum': 6,
                     'title': 'Decimals (default 0 for counts, 2 otherwise)'},
        'prefix': {'type': 'string', 'maxLength': 8,
                   'title': 'Before the value (e.g. $)'},
        'suffix': {'type': 'string', 'maxLength': 8, 'title': 'After the value'},
        'icon': {'type': 'string', 'pattern': ICON.pattern.replace('{1,80}', '*'),
                 'title': 'Icon (CSS class)'},
        'compare': {'type': 'boolean', 'default': True,
                    'title': 'Compare with the previous period'},
        'higher_is_better': {'type': 'boolean', 'default': True,
                             'title': 'A rise is good news'},
        'condition': {'x-widget': 'condition', 'title': 'Shown only when'},
    },
}


def period_bounds(build, column, now=None):
    """``((start, end), (start, end))`` of the current and the previous
    period of ``build``, typed for ``column`` (a date or date-time Column).
    With ``to_date`` the previous one ends as far into it as today is into
    the current one."""
    today = timezone.localdate(now) if now is not None else timezone.localdate()
    current = query.period_range(column, {'period': build.period,
                                          'date': today.isoformat()})
    previous = query.period_range(column, {'period': build.period,
                                           'date': (current_start_date(current)
                                                    - datetime.timedelta(days=1))
                                           .isoformat()})
    if build.to_date:
        if column.kind == 'datetime':
            moment = now or timezone.now()
            elapsed = moment - current[0]
        else:
            elapsed = today + datetime.timedelta(days=1) - current[0]
        previous = (previous[0], min(previous[0] + elapsed, previous[1]))
    return current, previous


def current_start_date(bounds):
    start = bounds[0]
    if isinstance(start, datetime.datetime):
        return timezone.localtime(start).date() if timezone.is_aware(start) \
            else start.date()
    return start


def range_filter(name, bounds):
    return Q(**{name + '__gte': bounds[0], name + '__lt': bounds[1]})


def plain_number(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


def format_metric(metric, value, signed=False):
    """The text of ``value`` in the format of ``metric``; ``—`` for none."""
    if value is None:
        return '—'
    decimals = metric['decimals']
    number = value * 100 if metric['format'] == 'percent' else value
    sign = ''
    if signed:
        sign = '+' if number > 0 else ('−' if number < 0 else '')
        number = abs(number)
    text = formats.number_format(round(Decimal(str(number)), decimals), decimals,
                                 use_l10n=True, force_grouping=True)
    if metric['format'] == 'percent':
        text += ' %'
    return '%s%s%s%s' % (sign, metric['prefix'], text, metric['suffix'])


def metric_result(metric, value, previous, compared):
    """What a card shows: the value and, compared, the change."""
    result = {'key': metric['key'], 'label': metric['label'], 'icon': metric['icon'],
              'value': value, 'display': format_metric(metric, value),
              'compare': compared}
    if not compared:
        return result
    delta = change = trend = good = None
    if value is not None and previous is not None:
        delta = value - previous
        trend = 'up' if delta > 0 else ('down' if delta < 0 else 'flat')
        if delta:
            good = (delta > 0) == metric['higher_is_better']
        if previous:
            change = round(delta * 100.0 / abs(previous), 1)
    result.update({
        'previous': previous, 'previous_display': format_metric(metric, previous),
        'delta': delta, 'delta_display': format_metric(metric, delta, signed=True)
        if delta is not None else '—',
        'change': change,
        'change_display': ('%+.1f %%' % change).replace('-', '−')
        if change is not None else '',
        'trend': trend, 'good': good})
    return result


def visible_metrics(build, request):
    return [metric for metric in build.metrics
            if metric['condition'] is None
            or evaluate_condition(metric['condition'], request)]


def metric_values(build, source, request, queryset, now=None):
    """``[card]`` of the metrics whose condition holds, every one computed in
    a single aggregate query over ``queryset`` (the rows of the source after
    the filters of the page). A sum or a count of no rows is 0; an average,
    a minimum or a maximum of none is ``None``; the change in percent is
    ``None`` when the previous period is empty or zero."""
    metrics = visible_metrics(build, request)
    if not metrics:
        return []
    colmap = source.column_map(request)
    bounds = None
    if build.date_field:
        column = colmap.get(build.date_field)
        if column is None or column.kind not in DATE_KINDS:
            raise ValidationError({'detail': _('unknown column')})
        bounds = period_bounds(build, column, now)
    aggregates = {}
    try:
        for index, metric in enumerate(metrics):
            q = Q()
            for flt in metric['filters']:
                q &= query.filter_q(source, request, flt, colmap, queryset.model)
            name = metric['column'] or 'pk'
            make = METRIC_FUNCTIONS[metric['fn']]
            if bounds is not None:
                aggregates['m%d' % index] = make(
                    name, q & range_filter(build.date_field, bounds[0]))
                if metric['compare']:
                    aggregates['p%d' % index] = make(
                        name, q & range_filter(build.date_field, bounds[1]))
            else:
                aggregates['m%d' % index] = make(name, q if q else None)
    except DjangoValidationError as error:
        raise ValidationError({'detail': error.messages})
    values = queryset.order_by().aggregate(**aggregates)
    cards = []
    for index, metric in enumerate(metrics):
        value = plain_number(values.get('m%d' % index))
        compared = bounds is not None and metric['compare']
        previous = plain_number(values.get('p%d' % index)) if compared else None
        if metric['fn'] in ('count', 'count_distinct', 'sum'):
            value = value or 0
            previous = (previous or 0) if compared else None
        cards.append(metric_result(metric, value, previous, compared))
    return cards


class MetricsViewSet(RegionMixin, viewsets.ViewSet):
    """The cards of a ``metrics`` node after the page's filters
    (``?params=``): ``{'metrics': [card], 'html'}``."""

    def list(self, request, *args, **kwargs):
        cards = metric_values(self.build, self.source, request, self.rows_queryset())
        return Response({'metrics': cards,
                         'html': render_cards(self.build, cards)})


def render_cards(build, cards):
    labels = PERIOD_LABELS.get(build.period, ('', ''))
    return render_to_string('gtdesigns/components/metrics_cards.html', {
        'b': build, 'cards': cards,
        'col': {1: 12, 2: 6, 3: 4, 4: 3, 6: 2}.get(build.per_row, 3),
        'current_label': labels[0] if build.date_field else '',
        'compare_label': labels[1]})


class MetricsComponent(RegionComponent):
    """KPI cards: an aggregate per card over the rows of a data source, with
    the change against the previous period."""

    type = 'metrics'
    label = gettext_lazy('Metric cards')
    icon = 'fa fa-tachometer'
    build_class = MetricsBuild
    template = 'gtdesigns/components/metrics.html'
    viewset = MetricsViewSet
    roles = {'date_field': (DATE_KINDS, False)}
    default_props = {'period': 'month',
                     'metrics': [{'label': 'Rows', 'fn': 'count'}]}
    props_schema = {
        'type': 'object',
        'required': ['metrics'],
        'additionalProperties': False,
        'properties': {
            **{name: schema for name, schema in common_properties().items()
               if name in ('model', 'datasource', 'site_field', 'title',
                           'filtered_by', 'perms')},
            'metrics': {'type': 'array', 'minItems': 1, 'maxItems': MAX_METRICS,
                        'x-widget': 'metrics', 'title': 'Cards',
                        'items': METRIC_SCHEMA},
            'date_field': column_prop('Date the periods are counted by (optional)',
                                      'date'),
            'period': {'enum': list(query.PERIODS), 'default': 'month',
                       'title': 'Period (with a date field)'},
            'to_date': {'type': 'boolean', 'default': False,
                        'title': 'Compare with the same stretch of the previous '
                                 'period, not the whole of it'},
            'per_row': {'enum': [1, 2, 3, 4, 6], 'title': 'Cards per row on a wide '
                                                          'screen'},
        },
    }

    def resolve_more(self, build, props, rctx, path, columns):
        build.period = props.get('period', 'month')
        build.to_date = props.get('to_date', False)
        build.per_row = props.get('per_row', 4)
        build.metrics = []
        for index, spec in enumerate(props.get('metrics') or []):
            metric = self.resolve_metric(build, spec, rctx,
                                         '%s.props.metrics[%d]' % (path, index),
                                         columns)
            if metric is not None:
                metric['key'] = 'm%d' % index
                build.metrics.append(metric)

    def resolve_metric(self, build, spec, rctx, where, columns):
        fn = spec.get('fn', 'count')
        name = spec.get('column') or ''
        if name:
            column = columns.get(name)
            if column is None:
                rctx.error(where + '.column', _('unknown column %r') % (name,))
                return None
            if fn in ('sum', 'avg', 'min', 'max') and not column.aggregatable:
                rctx.error(where + '.column', _('%(fn)s needs a numeric column; '
                                                '%(column)r is not one')
                           % {'fn': fn, 'column': name})
                return None
            build.labels[name] = str(column.label)
            build.kinds[name] = column.kind
        elif fn != 'count':
            rctx.error(where + '.column', _('%s needs a column') % fn)
            return None
        filters = list(spec.get('filters') or [])
        for position, flt in enumerate(filters):
            try:
                query.filter_q(None, None, flt, columns, build.model)
            except DjangoValidationError as error:
                rctx.error('%s.filters[%d]' % (where, position),
                           '; '.join(error.messages))
        condition = spec.get('condition')
        if condition is not None:
            errors = validate_condition(condition, where + '.condition')
            if errors:
                rctx.errors.extend(errors)
        counts = fn in ('count', 'count_distinct')
        return {'label': spec.get('label', ''), 'fn': fn, 'column': name,
                'filters': filters, 'format': spec.get('format', 'number'),
                'decimals': spec.get('decimals', 0 if counts else 2),
                'prefix': spec.get('prefix', ''), 'suffix': spec.get('suffix', ''),
                'icon': clean_icon(spec.get('icon')),
                'compare': spec.get('compare', True),
                'higher_is_better': spec.get('higher_is_better', True),
                'condition': condition}

    def render(self, build, rctx, children):
        if build.model is None and not build.datasource:
            return mark_safe('')
        if rctx.preview:
            return render_to_string(self.template, {
                'b': build, 'preview': True,
                'cards_html': render_cards(build, self.sample(build))})
        if build.perms and not can(rctx, build.perms):
            return no_permission(build)
        source = region_source(build)
        if source is None or rctx.request is None or \
                not source.has_permission(rctx.request):
            return no_permission(build)
        url = endpoint_url(rctx, build)
        if url is None:
            return no_permission(build)
        try:
            cards = metric_values(build, source, rctx.request,
                                  query.apply_params(source, rctx.request, {}))
            unavailable = False
        except (APIException, PermissionDenied, DjangoValidationError):
            # A data source that is down: the page stays, the cards say so.
            cards, unavailable = [], True
        return render_to_string(self.template, {
            'b': build, 'preview': False, 'unavailable': unavailable,
            'cards_html': render_cards(build, cards),
            'config': json_config(build.id + '_gtconfig',
                                  config_with_source(self, build, rctx, url))})

    def sample(self, build):
        cards = []
        for index, metric in enumerate(build.metrics):
            value, previous = 40 + index * 7, 36 + index * 9
            cards.append(metric_result(metric, value, previous,
                                       bool(build.date_field) and metric['compare']))
        return cards

    def media(self, build, rctx):
        return {'js': [SCRIPT], 'css': [STYLE]}


TREE_TIMELINE_METRICS_COMPONENTS = [TreeComponent, TimelineComponent,
                                    MetricsComponent]
