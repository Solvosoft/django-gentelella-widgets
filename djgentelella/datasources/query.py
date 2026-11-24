"""The query engine: JSON parameters run against a data source with the ORM.

The parameters are one JSON document, the one a saved report stores::

    {"search": "text",
     "filters": [{"column": "estado", "op": "in", "value": ["A", "B"]}],
     "ordering": ["-fecha"],
     "columns": ["id", "cliente", "total"],
     "group_by": ["estado"],
     "aggregates": [{"column": "total", "fn": "sum"}],
     "pivot": {"rows": "cliente", "columns": "estado",
               "value": {"column": "total", "fn": "sum"}},
     "highlights": [{"filter": {"column": "total", "op": "gt", "value": 1000},
                     "css": "table-danger"}]}

Everything is checked against ``source.columns(request)`` before it reaches
the ORM: an unknown column, an operator its kind does not allow or a value
that cannot be read as that kind raise ``ValidationError``, so a parameter
document is never a way to reach a field the source did not expose.
"""

import datetime
import json
import math
import re
from decimal import Decimal, InvalidOperation

from django.apps import apps
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import connections
from django.db.models import (
    Avg, Case, Count, DateField, DecimalField, F, FloatField, IntegerField, Max,
    Min, Q, Sum, Value, When,
)
from django.db.models.functions import (
    Coalesce, TruncDay, TruncMonth, TruncQuarter, TruncWeek, TruncYear,
)
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.translation import gettext as _

from djgentelella.designs.jsonschema import Error

from .base import DATE_KINDS, NUMERIC_KINDS, TEXT_KINDS

OPERATORS = ('eq', 'ne', 'lt', 'lte', 'gt', 'gte', 'in', 'contains',
             'icontains', 'startswith', 'isnull', 'between', 'date_period')

_ORDERED = ('eq', 'ne', 'lt', 'lte', 'gt', 'gte', 'in', 'between', 'isnull')
_TEXT = ('eq', 'ne', 'in', 'contains', 'icontains', 'startswith', 'isnull')

#: The operators each column kind accepts.
OPERATORS_BY_KIND = {
    'string': _TEXT,
    'text': _TEXT,
    'integer': _ORDERED,
    'decimal': _ORDERED,
    'boolean': ('eq', 'ne', 'isnull'),
    'date': _ORDERED + ('date_period',),
    'datetime': _ORDERED + ('date_period',),
    'fk': ('eq', 'ne', 'in', 'isnull'),
    'm2m': ('eq', 'in', 'isnull'),
    'choices': ('eq', 'ne', 'in', 'isnull'),
    'json': ('eq', 'ne', 'isnull'),
}

#: Aggregate functions. ``count`` and ``count_distinct`` take any column (and
#: ``count`` no column at all); ``sum`` and ``avg`` need an aggregatable one;
#: ``min`` and ``max`` an aggregatable or a date one.
FUNCTIONS = {
    'count': lambda name: Count(name),
    'count_distinct': lambda name: Count(name, distinct=True),
    'sum': Sum,
    'avg': Avg,
    'min': Min,
    'max': Max,
}

#: Periods for ``date_period`` filters and ``{"column", "period"}`` grouping.
PERIODS = {
    'year': TruncYear,
    'quarter': TruncQuarter,
    'month': TruncMonth,
    'week': TruncWeek,
    'day': TruncDay,
}

_LOOKUPS = {
    'eq': 'exact', 'lt': 'lt', 'lte': 'lte', 'gt': 'gt', 'gte': 'gte',
    'in': 'in', 'contains': 'contains', 'icontains': 'icontains',
    'startswith': 'startswith', 'isnull': 'isnull', 'between': 'range',
}

_PARAM_KEYS = ('search', 'filters', 'ordering', 'columns', 'group_by',
               'aggregates', 'pivot', 'highlights')

_WORD = re.compile(r'\w+')
_SEARCH_SYNTAX = re.compile(r'"|(^|\s)-|\bor\b', re.IGNORECASE)

#: How many values a facet lists, and in how many ranges a numeric one is cut.
FACET_LIMIT = 50
FACET_BUCKETS = 5


# -- parameters -------------------------------------------------------------

def parse_params(params):
    """Normalize a parameter document: a dict, a JSON string or None.

    Unknown top level keys are ignored (a saved report may carry its own),
    the known ones are type checked. Returns a new dict with every key.
    """
    if params is None or params == '':
        params = {}
    if isinstance(params, (str, bytes)):
        try:
            params = json.loads(params)
        except ValueError as e:
            raise ValidationError(_('The query parameters are not valid JSON: %s')
                                  % e)
    if not isinstance(params, dict):
        raise ValidationError(_('The query parameters must be a JSON object.'))
    defaults = {'search': '', 'filters': [], 'ordering': [], 'columns': [],
                'group_by': [], 'aggregates': [], 'pivot': None,
                'highlights': []}
    result = {key: (default if params.get(key) is None else params[key])
              for key, default in defaults.items()}
    if not isinstance(result['search'], str):
        raise ValidationError(_('"search" must be a string.'))
    for key in ('filters', 'ordering', 'columns', 'group_by', 'aggregates',
                'highlights'):
        if isinstance(result[key], str) and key in ('ordering', 'columns',
                                                    'group_by'):
            result[key] = [item for item in result[key].split(',') if item]
        if not isinstance(result[key], list):
            raise ValidationError(_('"%s" must be a list.') % key)
    for flt in result['filters']:
        if not isinstance(flt, dict):
            raise ValidationError(_('Each filter must be an object.'))
    if result['pivot'] is not None and not isinstance(result['pivot'], dict):
        raise ValidationError(_('"pivot" must be an object.'))
    return result


def _column(colmap, name, what=None):
    if not isinstance(name, str) or name not in colmap:
        raise ValidationError(_('Unknown column: %s') % (name,))
    column = colmap[name]
    if what is not None and not getattr(column, what):
        raise ValidationError(_('Column %(column)s is not %(what)s.') % {
            'column': name, 'what': what})
    return column


# -- values -----------------------------------------------------------------

_TRUE = ('1', 'true', 'yes', 'on', 't', 'y')
_FALSE = ('0', 'false', 'no', 'off', 'f', 'n')


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str) and value.lower() in _TRUE + _FALSE:
        return value.lower() in _TRUE
    raise ValueError(value)


def _as_date(value):
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    parsed = parse_date(str(value)) if value is not None else None
    if parsed is None:
        dt = parse_datetime(str(value)) if value is not None else None
        if dt is None:
            raise ValueError(value)
        parsed = dt.date()
    return parsed


def _as_datetime(value):
    if isinstance(value, datetime.datetime):
        parsed = value
    elif isinstance(value, datetime.date):
        parsed = datetime.datetime.combine(value, datetime.time.min)
    else:
        parsed = parse_datetime(str(value))
        if parsed is None:
            parsed = datetime.datetime.combine(_as_date(value), datetime.time.min)
    if timezone.is_naive(parsed) and timezone.get_current_timezone() is not None:
        parsed = timezone.make_aware(parsed)
    return parsed


def _date_only(value):
    """True for a date given without a time, "2026-01-31" or a date."""
    if isinstance(value, datetime.datetime):
        return False
    if isinstance(value, datetime.date):
        return True
    return isinstance(value, str) and parse_date(value) is not None


#: Largest power of ten (either way) of a ``decimal`` value. PostgreSQL's
#: ``numeric`` refuses a parameter past 131072 digits before the point or
#: 16383 after it, a ``float`` column overflows long before, and nobody
#: filters by a number this long.
MAX_DECIMAL_EXPONENT = 1000


def check_decimal(column, number):
    """``number`` if a ``decimal`` column can be compared with it; ValueError
    for ``NaN``, an infinity, a number past :data:`MAX_DECIMAL_EXPONENT` or one
    with more whole digits than the column's ``max_digits - decimal_places``
    (when the column says them)."""
    if not number.is_finite():
        raise ValueError(number)
    if number.is_zero():
        return number
    if abs(number.adjusted()) > MAX_DECIMAL_EXPONENT or (
            number.as_tuple().exponent < -MAX_DECIMAL_EXPONENT):
        raise ValueError(number)
    max_digits = getattr(column, 'max_digits', None)
    places = getattr(column, 'decimal_places', None)
    if max_digits is not None and places is not None and (
            number.adjusted() >= max_digits - places):
        raise ValueError(number)
    return number


def coerce_value(column, value, target=None):
    """``value`` read as a value of ``column``'s kind; ValidationError if not.

    ``target`` is the model field a ``fk``/``m2m`` value is compared with (the
    related primary key); its ``to_python`` reads the value when given. A
    ``decimal`` value has to be finite and fit the column
    (:func:`check_decimal`).
    """
    kind = column.kind
    try:
        if value is None:
            raise ValueError(value)
        if kind == 'integer':
            if isinstance(value, bool):
                raise ValueError(value)
            number = Decimal(str(value))
            if number != number.to_integral_value():
                raise ValueError(value)
            return int(number)
        if kind == 'decimal':
            if isinstance(value, bool):
                raise ValueError(value)
            return check_decimal(column, Decimal(str(value)))
        if kind == 'boolean':
            return _as_bool(value)
        if kind == 'date':
            return _as_date(value)
        if kind == 'datetime':
            return _as_datetime(value)
        if kind == 'choices' and column.choices:
            for key, _label in column.choices:
                if str(key) == str(value):
                    return key
            raise ValueError(value)
        if kind in TEXT_KINDS:
            if isinstance(value, (dict, list)):
                raise ValueError(value)
            return str(value)
        if kind in ('fk', 'm2m'):
            if isinstance(value, (dict, list, bool)):
                raise ValueError(value)
            if target is not None:
                return target.to_python(value)
            return value
        return value
    except (ValueError, TypeError, InvalidOperation, ArithmeticError,
            ValidationError):
        raise ValidationError(_('%(value)r is not a valid value for %(column)s.')
                              % {'value': value, 'column': column.name})


def period_range(column, value):
    """``[start, end)`` of a ``date_period`` value, typed for ``column``.

    The value is ``{"period": "month", "date": "2026-10-15"}`` (the period
    that holds that date) or ``{"period": "month", "offset": -1}`` (periods
    away from today: 0 is the current one, -1 the previous).
    """
    if not isinstance(value, dict) or not isinstance(value.get('period'), str) \
            or value['period'] not in PERIODS:
        raise ValidationError(_('date_period needs {"period": %s, "date"|'
                                '"offset"}.') % '|'.join(PERIODS))
    period = value['period']
    try:
        if 'date' in value and value['date'] not in (None, ''):
            ref = _as_date(value['date'])
            offset = 0
        else:
            ref = timezone.localdate()
            offset = int(value.get('offset') or 0)
        start = _period_start(ref, period)
        start = _shift(start, period, offset)
        end = _shift(start, period, 1)
    except (ValueError, TypeError, OverflowError):
        # Also an offset that leaves the calendar (year 0 or 10000).
        raise ValidationError(_('date_period: invalid date or offset.'))
    if column.kind == 'datetime':
        return _as_datetime(start), _as_datetime(end)
    return start, end


def _period_start(day, period):
    if period == 'year':
        return day.replace(month=1, day=1)
    if period == 'quarter':
        return day.replace(month=(day.month - 1) // 3 * 3 + 1, day=1)
    if period == 'month':
        return day.replace(day=1)
    if period == 'week':
        return day - datetime.timedelta(days=day.weekday())
    return day


def _shift(day, period, count):
    if period in ('year', 'quarter', 'month'):
        months = {'year': 12, 'quarter': 3, 'month': 1}[period] * count
        index = day.year * 12 + day.month - 1 + months
        return day.replace(year=index // 12, month=index % 12 + 1)
    days = 7 if period == 'week' else 1
    return day + datetime.timedelta(days=days * count)


# -- filters ----------------------------------------------------------------

def related_target(model, column):
    """The field a ``fk``/``m2m`` column's values are compared with (the
    related primary key, or the ``to_field``); None if it cannot be told."""
    if model is None or column.kind not in ('fk', 'm2m'):
        return None
    current = model
    field = None
    try:
        for part in column.name.split('__'):
            if current is None:
                return None
            field = current._meta.get_field(part)
            current = field.related_model if field.is_relation else None
    except FieldDoesNotExist:
        # An annotation of a FunctionDataSource's queryset.
        return None
    if current is None:
        return None
    target = getattr(field, 'target_field', None)
    if target is None or not hasattr(target, 'to_python'):
        target = current._meta.pk
    return target


def filter_q(source, request, flt, colmap=None, model=None):
    """The ``Q`` of one filter ``{"column", "op", "value"}``."""
    colmap = colmap if colmap is not None else source.column_map(request)
    column = _column(colmap, flt.get('column'), 'filterable')
    op = flt.get('op', 'eq')
    if op not in OPERATORS:
        raise ValidationError(_('Unknown operator: %s') % (op,))
    if op not in OPERATORS_BY_KIND[column.kind]:
        raise ValidationError(_('Operator %(op)s is not allowed on %(column)s '
                                '(%(kind)s).') % {'op': op, 'column': column.name,
                                                  'kind': column.kind})
    value = flt.get('value')
    name = column.name
    target = related_target(model, column)
    if op == 'isnull':
        try:
            value = _as_bool(True if value is None else value)
        except ValueError:
            raise ValidationError(_('isnull takes true or false.'))
        q = Q(**{name + '__isnull': value})
    elif op == 'date_period':
        start, end = period_range(column, value)
        q = Q(**{name + '__gte': start, name + '__lt': end})
    elif op == 'in':
        if not isinstance(value, (list, tuple)):
            value = [value] if value not in (None, '') else []
        q = Q(**{name + '__in': [coerce_value(column, v, target)
                                 for v in value]})
    elif op == 'between':
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ValidationError(_('between takes a list of two values.'))
        low, high = (coerce_value(column, v, target)
                     if v not in (None, '') else None for v in value)
        q = Q()
        if low is not None:
            q &= Q(**{name + '__gte': low})
        if high is not None:
            if column.kind == 'datetime' and _date_only(value[1]):
                # "To 2026-01-31" on a datetime means the whole of that day.
                q &= Q(**{name + '__lt': high + datetime.timedelta(days=1)})
            else:
                q &= Q(**{name + '__lte': high})
    else:
        lookup = _LOOKUPS['eq' if op == 'ne' else op]
        value = coerce_value(column, value, target)
        q = Q(**{'%s__%s' % (name, lookup): value})
    if column.kind == 'm2m' and model is not None:
        # Through a subquery, so a row that matches on two related objects is
        # still one row -- no distinct() that would then fight the aggregates.
        q = Q(pk__in=_filter(model._default_manager, q).values('pk'))
    if op == 'ne':
        # SQL drops NULL from a negated comparison; "not equal" keeps it.
        q = ~q | Q(**{name + '__isnull': True})
    return q


def apply_filters(source, request, queryset, filters, colmap=None,
                  skip_columns=()):
    colmap = colmap if colmap is not None else source.column_map(request)
    for flt in filters:
        if flt.get('column') in skip_columns:
            continue
        q = filter_q(source, request, flt, colmap, queryset.model)
        queryset = _filter(queryset, q)
    return queryset


def _filter(queryset, *args, **kwargs):
    """``queryset.filter()``, with a value the ORM cannot prepare (a field
    that ``coerce_value`` does not know the type of) as a ValidationError."""
    try:
        return queryset.filter(*args, **kwargs)
    except (ValueError, TypeError, OverflowError) as e:
        raise ValidationError(_('Invalid filter value: %s') % (e,))


# -- search -----------------------------------------------------------------

def use_fulltext(source, queryset):
    mode = getattr(source, 'search_mode', 'auto')
    if mode == 'icontains':
        return False
    available = (connections[queryset.db].vendor == 'postgresql'
                 and apps.is_installed('django.contrib.postgres'))
    if mode == 'fulltext' and not available:
        raise ValidationError(_('Full-text search needs PostgreSQL and '
                                'django.contrib.postgres.'))
    return available


def apply_search(source, request, queryset, text, colmap=None):
    """``icontains`` over the text columns, or full-text on PostgreSQL."""
    text = (text or '').strip()
    if not text:
        return queryset
    colmap = colmap if colmap is not None else source.column_map(request)
    names = [c.name for c in colmap.values() if c.kind in TEXT_KINDS]
    if not names:
        return queryset
    if use_fulltext(source, queryset):
        # Optional dependency: importing it needs psycopg, which only a
        # PostgreSQL project has installed.
        from django.contrib.postgres.search import SearchVector  # noqa: PLC0415
        config = getattr(source, 'search_config', None)
        vector = SearchVector(*names, config=config)
        query = fulltext_query(text, config)
        return queryset.annotate(_gt_search=vector).filter(_gt_search=query)
    q = Q()
    for name in names:
        q |= Q(**{name + '__icontains': text})
    return queryset.filter(q)


def fulltext_query(text, config=None):
    """The ``SearchQuery`` of a search box text (PostgreSQL only).

    Plain words are prefixes, all required: a box finds "Gamma" while "gam"
    is still being typed. A text with quotes, "or" or a leading "-" is read
    with the web search syntax. The global search uses it too.
    """
    # Optional dependency: importing it needs psycopg, which only a
    # PostgreSQL project has installed.
    from django.contrib.postgres.search import SearchQuery  # noqa: PLC0415
    words = _WORD.findall(text)
    if words and not _SEARCH_SYNTAX.search(text):
        # Built from \w+ only, so the raw tsquery cannot carry operators of
        # its own.
        return SearchQuery(' & '.join(w + ':*' for w in words),
                           search_type='raw', config=config)
    return SearchQuery(text, search_type='websearch', config=config)


# -- ordering ---------------------------------------------------------------

def ordering_args(colmap, ordering):
    result = []
    for item in ordering:
        if not isinstance(item, str) or not item.lstrip('-'):
            raise ValidationError(_('Invalid ordering: %r') % (item,))
        _column(colmap, item.lstrip('-'), 'sortable')
        result.append(item)
    return result


def apply_params(source, request, params):
    """The source queryset with the filters, the search and the ordering.

    ``columns``, ``group_by``, ``aggregates``, ``pivot`` and ``highlights``
    are read by the functions that use them, not here.
    """
    params = parse_params(params)
    colmap = source.column_map(request)
    queryset = source.get_queryset(request)
    queryset = apply_filters(source, request, queryset, params['filters'], colmap)
    queryset = apply_search(source, request, queryset, params['search'], colmap)
    order = ordering_args(colmap, params['ordering'])
    if not any(item.lstrip('-') == 'pk' for item in order):
        # Stable pages: without a unique last key a row can show up twice.
        order.append('pk')
    return queryset.order_by(*order)


def selected_columns(source, request, params):
    """The columns to show: ``params["columns"]`` or all of them."""
    params = parse_params(params)
    colmap = source.column_map(request)
    if not params['columns']:
        return list(colmap.values())
    return [_column(colmap, name) for name in params['columns']]


# -- grouping and aggregates ------------------------------------------------

def group_expr(colmap, item, index=0):
    """``(alias, output name, expression or None, column, period)`` for a
    ``group_by`` entry: a column name or ``{"column", "period"}``.

    ValidationError when the entry cannot be grouped by: an unknown column, a
    ``m2m`` one, or a period that is not one of :data:`PERIODS` or is given
    on a column that is not a date. ``colmap`` is ``source.column_map()``.
    """
    period = None
    if isinstance(item, dict):
        name = item.get('column')
        period = item.get('period')
    else:
        name = item
    column = _column(colmap, name)
    if column.kind == 'm2m':
        raise ValidationError(_('Cannot group by %s.') % name)
    if period is not None:
        if not isinstance(period, str) or period not in PERIODS or (
                column.kind not in DATE_KINDS):
            raise ValidationError(_('Invalid period %(period)r for %(column)s.')
                                  % {'period': period, 'column': name})
        return ('_gt_g%d' % index, name,
                PERIODS[period](name, output_field=DateField()), column, period)
    return name, name, None, column, None


def aggregate_expr(colmap, spec):
    """``(output key, expression)`` of an aggregate ``{"column", "fn"}``.

    ValidationError when it cannot run: not an object, an unknown function or
    column, ``sum``/``avg`` on a column that is not aggregatable, ``min``/
    ``max`` on one that is neither aggregatable nor a date.
    """
    if not isinstance(spec, dict):
        raise ValidationError(_('Each aggregate must be an object.'))
    fn = spec.get('fn')
    if not isinstance(fn, str) or fn not in FUNCTIONS:
        raise ValidationError(_('Unknown aggregate function: %s') % (fn,))
    name = spec.get('column')
    if fn == 'count' and name in (None, '', '*'):
        return 'count', Count('pk')
    column = _column(colmap, name)
    if fn in ('sum', 'avg') and not column.aggregatable:
        raise ValidationError(_('%(fn)s is not allowed on %(column)s.')
                              % {'fn': fn, 'column': name})
    if fn in ('min', 'max') and not (column.aggregatable
                                     or column.kind in DATE_KINDS):
        raise ValidationError(_('%(fn)s is not allowed on %(column)s.')
                              % {'fn': fn, 'column': name})
    return '%s__%s' % (name, fn), FUNCTIONS[fn](name)


# Private aliases kept for callers that import them under these names.
_group_expr = group_expr
_aggregate_expr = aggregate_expr


def max_groups():
    """``GT_DATASOURCE_MAX_GROUPS``: how many groups :func:`aggregate` and how
    many rows and columns :func:`pivot` return at most (1000)."""
    return int(getattr(settings, 'GT_DATASOURCE_MAX_GROUPS', 1000))


def _too_many(what, limit):
    return ValidationError(
        _('More than %(limit)d %(what)s: add a filter, or group by a column '
          'with fewer values.') % {'limit': limit, 'what': what})


def _value_ordering(queryset, alias):
    """Largest ``alias`` first, an empty aggregate counted as 0 (as a chart
    draws it); a date aggregate with the empty ones last."""
    output = queryset.query.annotations[alias].output_field
    if isinstance(output, (IntegerField, FloatField, DecimalField)):
        return Coalesce(F(alias), Value(0, output_field=output),
                        output_field=output).desc()
    return F(alias).desc(nulls_last=True)


def aggregate(source, request, params, *, order_by_value=False, limit=None):
    """Group by ``group_by`` and compute ``aggregates``.

    One dict per group with the group values under the column names and each
    aggregate under ``"<column>__<fn>"`` (``"count"`` for a bare count). A
    group by a ``fk`` or ``choices`` column also carries
    ``"<column>__display"``. Without ``group_by`` the list has one dict, the
    totals.

    The groups come in the order of their values; with ``order_by_value``,
    from the largest first aggregate down. ``limit`` keeps the first ones
    (in the database). Without it, more than ``GT_DATASOURCE_MAX_GROUPS``
    groups is a ``ValidationError``: a group by a column with a value per
    row would otherwise load the whole table.
    """
    params = parse_params(params)
    colmap = source.column_map(request)
    queryset = apply_params(source, request, params)
    specs = params['aggregates'] or [{'fn': 'count'}]
    aggs = []
    for index, spec in enumerate(specs):
        key, expr = aggregate_expr(colmap, spec)
        aggs.append(('_gt_a%d' % index, key, expr))
    if not params['group_by']:
        values = queryset.order_by().aggregate(**{a: e for a, _k, e in aggs})
        return [{key: values[alias] for alias, key, _e in aggs}]
    groups = [group_expr(colmap, item, i)
              for i, item in enumerate(params['group_by'])]
    annotations = {alias: expr for alias, _n, expr, _c, _p in groups if expr}
    queryset = queryset.order_by()
    if annotations:
        queryset = queryset.annotate(**annotations)
    aliases = [alias for alias, *_rest in groups]
    queryset = queryset.values(*aliases).annotate(**{a: e for a, _k, e in aggs})
    ordering = list(aliases)
    if order_by_value:
        ordering.insert(0, _value_ordering(queryset, aggs[0][0]))
    queryset = queryset.order_by(*ordering)
    cap = max_groups()
    if limit is not None and limit <= cap:
        rows = list(queryset[:max(limit, 0)])
    else:
        rows = list(queryset[:cap + 1])
        if len(rows) > cap:
            raise _too_many(_('groups'), cap)
        if limit is not None:
            rows = rows[:limit]
    result = []
    for row in rows:
        item = {}
        for alias, name, _expr, _col, _period in groups:
            item[name] = row[alias]
        for alias, key, _e in aggs:
            item[key] = row[alias]
        result.append(item)
    for _alias, name, _expr, column, period in groups:
        if period is None and column.kind in ('fk', 'choices'):
            labels = value_labels(source, request, column,
                                  [item[name] for item in result],
                                  queryset.model)
            for item in result:
                item[name + '__display'] = labels.get(item[name], item[name])
    return result


def pivot(source, request, params):
    """Cross tab of ``pivot["rows"]`` by ``pivot["columns"]``.

    Returns ``{"rows": [...], "columns": [...], "data": [[...]]}`` where
    ``data[i][j]`` is the value for ``rows[i]`` and ``columns[j]``, plus
    ``row_labels`` and ``column_labels``. When the pivot columns are known in
    advance (a ``choices`` or ``boolean`` column) the whole table is one
    ``values().annotate()`` query with one ``Case/When`` aggregate per column;
    otherwise the column values come from the data and the table is composed
    in Python from a grouped query.

    More than ``GT_DATASOURCE_MAX_GROUPS`` rows, or columns, is a
    ``ValidationError``.
    """
    params = parse_params(params)
    spec = params['pivot']
    if not spec:
        raise ValidationError(_('"pivot" is required.'))
    colmap = source.column_map(request)
    row_alias, row_name, row_expr, row_col, row_period = group_expr(
        colmap, spec.get('rows'), 0)
    col_alias, col_name, col_expr, col_col, col_period = group_expr(
        colmap, spec.get('columns'), 1)
    value = spec.get('value') or {'fn': 'count'}
    _key, agg = aggregate_expr(colmap, value)
    fn = value.get('fn')
    queryset = apply_params(source, request, params).order_by()
    annotations = {a: e for a, e in ((row_alias, row_expr), (col_alias, col_expr))
                   if e is not None}
    if annotations:
        queryset = queryset.annotate(**annotations)

    cap = max_groups()
    static = col_period is None and col_col.kind in ('choices', 'boolean')
    if static:
        if col_col.kind == 'boolean':
            col_values = [True, False]
        else:
            col_values = [key for key, _label in col_col.choices or ()]
        target = value.get('column')
        cases = {}
        for index, cvalue in enumerate(col_values):
            when = When(Q(**{col_name: cvalue}),
                        then=F(target) if target not in (None, '', '*')
                        else F('pk'))
            cases['_gt_p%d' % index] = _case_aggregate(fn, Case(when))
        rows_qs = queryset.values(row_alias).annotate(**cases).order_by(row_alias)
        row_values = []
        data = []
        for row in rows_qs[:cap + 1]:
            row_values.append(row[row_alias])
            data.append([row['_gt_p%d' % i] for i in range(len(col_values))])
        if len(row_values) > cap:
            raise _too_many(_('rows'), cap)
    else:
        grouped = queryset.values(row_alias, col_alias).annotate(
            _gt_v=agg).order_by(row_alias, col_alias)
        cells = {}
        # dicts as ordered sets: the values in the order they first appear.
        seen_rows, seen_columns = {}, {}
        for row in grouped.iterator():
            rvalue, cvalue = row[row_alias], row[col_alias]
            seen_rows.setdefault(rvalue)
            seen_columns.setdefault(cvalue)
            if len(seen_rows) > cap:
                raise _too_many(_('rows'), cap)
            if len(seen_columns) > cap:
                raise _too_many(_('columns'), cap)
            cells[(rvalue, cvalue)] = row['_gt_v']
        row_values = list(seen_rows)
        col_values = _sorted_values(list(seen_columns))
        empty = 0 if fn in ('count', 'count_distinct') else None
        data = [[cells.get((r, c), empty) for c in col_values]
                for r in row_values]
    return {
        'rows': row_values,
        'columns': col_values,
        'data': data,
        'row_labels': _labels_for(source, request, row_col, row_period,
                                  row_values, queryset.model),
        'column_labels': _labels_for(source, request, col_col, col_period,
                                     col_values, queryset.model),
    }


def _case_aggregate(fn, case):
    if fn == 'count':
        return Count(case)
    if fn == 'count_distinct':
        return Count(case, distinct=True)
    return FUNCTIONS[fn](case)


def _sorted_values(values):
    try:
        return sorted(values, key=lambda v: (v is None, v))
    except TypeError:
        return values


def _labels_for(source, request, column, period, values, model):
    if period is not None:
        return [period_label(period, v) for v in values]
    labels = value_labels(source, request, column, values, model)
    return [labels.get(v, v) for v in values]


# -- labels -----------------------------------------------------------------

def related_model(model, column):
    """The model a ``fk``/``m2m`` column points to, or None."""
    if model is None:
        return None
    current = model
    field = None
    for part in column.name.split('__'):
        if current is None:
            return None
        field = current._meta.get_field(part)
        current = field.related_model if field.is_relation else None
    return current


def value_labels(source, request, column, values, model=None):
    """``{value: label}`` for values of a ``fk``/``m2m``/``choices``/
    ``boolean`` column; values of other kinds are their own label.

    ``model`` is the model of the rows; ``source.model`` by default.
    """
    values = [v for v in values if v is not None]
    if column.kind == 'choices' and column.choices:
        mapping = {key: str(label) for key, label in column.choices}
        return {v: mapping.get(v, v) for v in values}
    if column.kind == 'boolean':
        return {True: _('Yes'), False: _('No')}
    if column.kind in ('fk', 'm2m'):
        model = related_model(model or getattr(source, 'model', None), column)
        if model is not None and values:
            return {pk: str(obj) for pk, obj in
                    model._default_manager.in_bulk(set(values)).items()}
    return {}


def period_label(period, value):
    if value is None:
        return _('Empty')
    if isinstance(value, datetime.datetime):
        value = value.date()
    if period == 'year':
        return '%d' % value.year
    if period == 'quarter':
        return '%d-Q%d' % (value.year, (value.month - 1) // 3 + 1)
    if period == 'month':
        return value.strftime('%Y-%m')
    return value.isoformat()


# -- facets -----------------------------------------------------------------

def facets(source, request, params, columns, limit=FACET_LIMIT,
           buckets=FACET_BUCKETS):
    """Counts per value of each column in ``columns``.

    The count of a facet applies every filter **but its own**, plus the
    search: picking a value of "estado" narrows the counts of the other
    facets and leaves the alternatives of "estado" visible, as APEX's
    Faceted Search does.

    Each entry is ``{"value", "label", "count", "op"}``, where ``op`` and
    ``value`` make the filter that selects it. Numeric columns come back as
    ``buckets`` ranges (``between``), date ones as periods (``date_period``):
    years, months or days depending on the span of the data.
    """
    params = parse_params(params)
    colmap = source.column_map(request)
    if isinstance(columns, str):
        columns = [name for name in columns.split(',') if name]
    base = source.get_queryset(request)
    base = apply_search(source, request, base, params['search'], colmap)
    result = {}
    for name in columns:
        column = _column(colmap, name, 'filterable')
        queryset = apply_filters(source, request, base, params['filters'],
                                 colmap, skip_columns=(name,)).order_by()
        if column.kind in NUMERIC_KINDS:
            result[name] = _numeric_facet(queryset, column, buckets)
        elif column.kind in DATE_KINDS:
            result[name] = _date_facet(queryset, column, limit)
        elif column.kind == 'json':
            raise ValidationError(_('Cannot facet on %s.') % name)
        else:
            result[name] = _value_facet(source, request, queryset, column, limit)
    return result


def _value_facet(source, request, queryset, column, limit):
    rows = list(queryset.values(column.name).annotate(
        _gt_count=Count('pk', distinct=True)).order_by('-_gt_count', column.name)
        [:limit])
    labels = value_labels(source, request, column,
                          [row[column.name] for row in rows], queryset.model)
    op = 'eq' if column.kind == 'boolean' else 'in'
    return [{
        'value': row[column.name],
        'label': (str(labels.get(row[column.name], row[column.name]))
                  if row[column.name] is not None else _('Empty')),
        'count': row['_gt_count'],
        'op': op if row[column.name] is not None else 'isnull',
    } for row in rows]


def _numeric_facet(queryset, column, buckets):
    name = column.name
    bounds = queryset.aggregate(low=Min(name), high=Max(name))
    low, high = bounds['low'], bounds['high']
    if low is None:
        return []
    ranges = numeric_ranges(column, low, high, buckets)
    counts = queryset.aggregate(**{
        '_gt_b%d' % i: Count('pk', filter=Q(**{name + '__range': (lo, hi)}))
        for i, (lo, hi) in enumerate(ranges)
    })
    return [{
        'value': [_plain(lo), _plain(hi)],
        'label': ('%s' % _plain(lo) if lo == hi
                  else '%s – %s' % (_plain(lo), _plain(hi))),
        'count': counts['_gt_b%d' % i],
        'op': 'between',
    } for i, (lo, hi) in enumerate(ranges)]


def numeric_ranges(column, low, high, buckets):
    """Up to ``buckets`` inclusive ranges that cover ``[low, high]``.

    Integer ranges never overlap. Decimal ones share their edges, so a value
    sitting exactly on one counts in both -- each count is still what the
    ``between`` filter of its range returns.
    """
    if column.kind == 'integer':
        low, high = int(low), int(high)
        width = max(1, math.ceil((high - low + 1) / buckets))
        ranges = []
        start = low
        while start <= high:
            ranges.append((start, min(high, start + width - 1)))
            start += width
        return ranges
    low, high = Decimal(str(low)), Decimal(str(high))
    if low == high:
        return [(low, high)]
    step = (high - low) / buckets
    # Two significant digits for the step keeps the labels readable.
    exponent = Decimal(10) ** (step.adjusted() - 1)
    step = (step / exponent).to_integral_value(rounding='ROUND_CEILING') * exponent
    ranges = []
    start = (low / exponent).to_integral_value(rounding='ROUND_FLOOR') * exponent
    while start <= high and len(ranges) < buckets + 1:
        ranges.append((start, start + step))
        start += step
    return ranges


def _plain(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


def _date_facet(queryset, column, limit):
    name = column.name
    bounds = queryset.aggregate(low=Min(name), high=Max(name))
    low, high = bounds['low'], bounds['high']
    if low is None:
        return []
    if isinstance(low, datetime.datetime):
        low, high = timezone.localtime(low).date(), timezone.localtime(high).date()
    span = (high - low).days
    period = 'year' if span > 731 else 'month' if span > 31 else 'day'
    rows = queryset.annotate(_gt_period=PERIODS[period](
        name, output_field=DateField())).values('_gt_period').annotate(
        _gt_count=Count('pk', distinct=True)).order_by('-_gt_period')[:limit]
    return [{
        'value': {'period': period, 'date': row['_gt_period'].isoformat()},
        'label': period_label(period, row['_gt_period']),
        'count': row['_gt_count'],
        'op': 'date_period',
    } for row in rows]


# -- rows -------------------------------------------------------------------

def serialize_rows(source, request, rows, columns, display=False):
    """The rows of the queryset ``rows`` (a page of it, typically) as dicts
    keyed by column name, plus ``pk``.

    JSON mode (``display=False``) keeps raw values and turns ``fk`` into
    ``{"id", "display_name"}`` and ``m2m`` into a list of those. Display mode
    (exports) turns ``fk``, ``m2m`` and ``choices`` into their text.
    """
    flat = [c.name for c in columns if c.kind != 'm2m']
    data = list(rows.values('pk', *flat))
    pks = [row['pk'] for row in data]
    for column in columns:
        if column.kind == 'm2m':
            related = {}
            through = rows.model._default_manager.filter(pk__in=pks).values_list(
                'pk', column.name)
            for pk, value in through:
                if value is not None:
                    related.setdefault(pk, []).append(value)
            labels = value_labels(source, request, column,
                                  [v for vs in related.values() for v in vs],
                                  rows.model)
            for row in data:
                values = related.get(row['pk'], [])
                if display:
                    row[column.name] = ', '.join(str(labels.get(v, v))
                                                 for v in values)
                else:
                    row[column.name] = [{'id': v, 'display_name':
                                         str(labels.get(v, v))} for v in values]
        elif column.kind == 'fk':
            labels = value_labels(source, request, column,
                                  [row[column.name] for row in data], rows.model)
            for row in data:
                value = row[column.name]
                if value is None:
                    row[column.name] = '' if display else None
                elif display:
                    row[column.name] = str(labels.get(value, value))
                else:
                    row[column.name] = {'id': value, 'display_name':
                                        str(labels.get(value, value))}
        elif column.kind == 'choices' and display:
            labels = value_labels(source, request, column,
                                  [row[column.name] for row in data], rows.model)
            for row in data:
                value = row[column.name]
                row[column.name] = '' if value is None else str(
                    labels.get(value, value))
    return data


def highlight_classes(source, request, queryset, pks, highlights, colmap=None):
    """``{pk: "css classes"}`` for the rows in ``pks`` that match a highlight
    rule ``{"filter": {...}, "css": "table-danger"}``."""
    if not highlights or not pks:
        return {}
    colmap = colmap if colmap is not None else source.column_map(request)
    result = {}
    for rule in highlights:
        if not isinstance(rule, dict) or not isinstance(rule.get('filter'), dict):
            raise ValidationError(_('Each highlight needs a "filter" object.'))
        css = str(rule.get('css') or 'table-warning')
        q = filter_q(source, request, rule['filter'], colmap, queryset.model)
        # On the source's own queryset: a column may be an annotation of it.
        matches = _filter(queryset.order_by(), q, pk__in=pks)
        for pk in matches.values_list('pk', flat=True):
            result[pk] = (result[pk] + ' ' + css) if pk in result else css
    return result


# -- validation -------------------------------------------------------------

#: One or more CSS class names: what a highlight may put in ``class=""``.
CSS_CLASSES = re.compile(r'^-?[A-Za-z_][\w-]*( -?[A-Za-z_][\w-]*)*$')
#: The keys of a ``group_by`` entry, of an aggregate, of a pivot and of a
#: highlight that :func:`validate_params` takes with ``strict``.
_GROUP_KEYS = ('column', 'period')
_AGGREGATE_KEYS = ('column', 'fn')
_PIVOT_KEYS = ('rows', 'columns', 'value')
_HIGHLIGHT_KEYS = ('filter', 'css', 'target', 'label')


def _messages(error):
    return error.messages if isinstance(error, ValidationError) else [str(error)]


def _unknown_keys(value, allowed, path, errors):
    unknown = sorted(str(key) for key in set(value) - set(allowed))
    if unknown:
        errors.append(Error(path, _('unknown keys: %s') % ', '.join(unknown)))


def validate_params(source, request, params, *, strict=False):
    """``(clean, errors)``: the parameter document checked against the
    columns of ``source`` without reading a row.

    ``clean`` is the document normalized as :func:`parse_params` returns it,
    or ``None`` when there are errors. ``errors`` is a list of
    :class:`~djgentelella.designs.jsonschema.Error` -- ``(path, message)``,
    such as ``$.filters[0]: Unknown column: x`` or ``$.aggregates[1]: sum is
    not allowed on nombre.`` -- with every problem found, not only the first.

    It checks what the query functions would refuse when they run: unknown
    columns, operators a column's kind does not take, values that cannot be
    read as that kind (decimals out of range included), the ``ordering``,
    the ``columns`` (each once), the ``group_by`` entries and the
    ``aggregates`` (:func:`group_expr`, :func:`aggregate_expr`), the
    ``pivot`` and the ``highlights`` (a ``filter``, and CSS class names in
    ``css``). With ``strict``, unknown keys are errors too; otherwise the top
    level ones are ignored, as :func:`parse_params` does. When all that
    passes and the user may read the source, the queryset is built (not run)
    so the ORM checks the values as well.
    """
    errors = []
    try:
        clean = parse_params(params)
    except ValidationError as error:
        return None, [Error('$', message) for message in _messages(error)]
    if strict and isinstance(params, dict):
        _unknown_keys(params, _PARAM_KEYS, '$', errors)
    colmap = source.column_map(request)
    model = getattr(source, 'model', None)

    def check(path, function, *args):
        try:
            return function(*args)
        except ValidationError as error:
            errors.extend(Error(path, message) for message in _messages(error))
        return None

    for index, flt in enumerate(clean['filters']):
        check('$.filters[%d]' % index, filter_q, source, request, flt, colmap, model)
    for index, item in enumerate(clean['ordering']):
        check('$.ordering[%d]' % index, ordering_args, colmap, [item])
    seen = set()
    for index, name in enumerate(clean['columns']):
        path = '$.columns[%d]' % index
        if check(path, _column, colmap, name) is None:
            continue
        if name in seen:
            errors.append(Error(path, _('Column %s is listed twice.') % name))
        seen.add(name)
    for index, item in enumerate(clean['group_by']):
        path = '$.group_by[%d]' % index
        if strict and isinstance(item, dict):
            _unknown_keys(item, _GROUP_KEYS, path, errors)
        check(path, group_expr, colmap, item, index)
    for index, spec in enumerate(clean['aggregates']):
        path = '$.aggregates[%d]' % index
        if strict and isinstance(spec, dict):
            _unknown_keys(spec, _AGGREGATE_KEYS, path, errors)
        check(path, aggregate_expr, colmap, spec)
    pivot_spec = clean['pivot']
    if pivot_spec is not None:
        if strict:
            _unknown_keys(pivot_spec, _PIVOT_KEYS, '$.pivot', errors)
        for index, key in enumerate(('rows', 'columns')):
            path = '$.pivot.%s' % key
            item = pivot_spec.get(key)
            if item in (None, ''):
                errors.append(Error(path, _('"pivot" needs "rows" and "columns".')))
                continue
            if strict and isinstance(item, dict):
                _unknown_keys(item, _GROUP_KEYS, path, errors)
            check(path, group_expr, colmap, item, index)
        if pivot_spec.get('value') is not None:
            check('$.pivot.value', aggregate_expr, colmap, pivot_spec['value'])
    for index, rule in enumerate(clean['highlights']):
        path = '$.highlights[%d]' % index
        if not isinstance(rule, dict) or not isinstance(rule.get('filter'), dict):
            errors.append(Error(path, _('Each highlight needs a "filter" object.')))
            continue
        if strict:
            _unknown_keys(rule, _HIGHLIGHT_KEYS, path, errors)
        check(path + '.filter', filter_q, source, request, rule['filter'], colmap,
              model)
        css = rule.get('css')
        if css is not None and (not isinstance(css, str)
                                or not CSS_CLASSES.match(css)):
            errors.append(Error(path + '.css',
                                _('%r is not a list of CSS classes.') % (css,)))
    if not errors and source.has_permission(request):
        # The ORM prepares each value only when the queryset is filtered.
        check('$', apply_params, source, request, clean)
    return (None, errors) if errors else (clean, [])
