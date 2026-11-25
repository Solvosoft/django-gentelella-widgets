"""Exports of a data source: CSV, XLSX, JSON and PDF.

Every exporter takes ``(source, request, params)`` and returns an
``HttpResponse``; :data:`EXPORTERS` maps a format name to one, and
:func:`register_exporter` adds or replaces formats (a project can add PDF
layouts of its own there). All of them honour the query parameters: the
filters, the search, the ordering, the ``columns`` picked, the ``aggregates``
(as a totals row) and the ``highlights``.

The XLSX exporter needs openpyxl (the ``export`` extra) and the PDF one
xhtml2pdf >= 0.2.28 (the ``pdf`` extra); both are imported only when used.
"""

import csv
import datetime
import json
import logging
import re
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse, StreamingHttpResponse
from django.template.loader import render_to_string
from django.utils import formats, timezone
from django.utils.text import slugify
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _, gettext_lazy

from .query import (
    aggregate_expr, apply_params, coerce_value, highlight_classes,
    parse_params, selected_columns, serialize_rows, validate_params,
)

logger = logging.getLogger(__name__)

#: Rows read from the database at a time while streaming.
CHUNK_SIZE = 1000

#: The fill of a highlight's css class in XLSX and PDF (Bootstrap 5 colors).
HIGHLIGHT_COLORS = {
    'table-primary': 'CFE2FF',
    'table-secondary': 'E2E3E5',
    'table-success': 'D1E7DD',
    'table-danger': 'F8D7DA',
    'table-warning': 'FFF3CD',
    'table-info': 'CFF4FC',
    'table-light': 'F8F9FA',
    'table-dark': 'ADB5BD',
}
DEFAULT_HIGHLIGHT_COLOR = 'FFF3CD'
HEX_COLOR = re.compile(r'^#([0-9a-fA-F]{6})$')

#: Control characters XML 1.0 does not allow, which openpyxl refuses to write
#: (the same set as ``openpyxl.cell.cell.ILLEGAL_CHARACTERS_RE``).
XLSX_ILLEGAL_CHARACTERS = re.compile(r'[\000-\010]|[\013-\014]|[\016-\037]')

#: First characters a spreadsheet reads as the start of a formula.
FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r')

FUNCTION_LABELS = {
    'count': gettext_lazy('Count'),
    'count_distinct': gettext_lazy('Distinct'),
    'sum': gettext_lazy('Sum'),
    'avg': gettext_lazy('Average'),
    'min': gettext_lazy('Min'),
    'max': gettext_lazy('Max'),
}

#: ``{format: exporter}`` of the formats every request has.
EXPORTERS = {}
#: Callables ``(request) -> {format: exporter}`` for the formats that depend
#: on the request -- the layouts of the current application, say. A request
#: has the formats of :data:`EXPORTERS` plus those of every resolver; a
#: resolver's format with the name of a static one replaces it there.
EXPORTER_RESOLVERS = []


def register_exporter(fmt):
    """Decorator: ``@register_exporter('pdf')`` makes the function the
    exporter of that format, replacing the one there was."""
    def decorator(fn):
        EXPORTERS[fmt] = fn
        return fn
    return decorator


def register_exporter_resolver(resolver):
    """Add ``resolver`` to :data:`EXPORTER_RESOLVERS` (once); usable as a
    decorator."""
    if resolver not in EXPORTER_RESOLVERS:
        EXPORTER_RESOLVERS.append(resolver)
    return resolver


def unregister_exporter_resolver(resolver):
    if resolver in EXPORTER_RESOLVERS:
        EXPORTER_RESOLVERS.remove(resolver)


def available_exporters(request):
    """``{format: exporter}`` for ``request``: :data:`EXPORTERS` and what
    each of :data:`EXPORTER_RESOLVERS` adds. A resolver that raises adds
    nothing (and is logged): one broken resolver does not take the other
    formats down."""
    found = dict(EXPORTERS)
    for resolver in list(EXPORTER_RESOLVERS):
        try:
            extra = resolver(request) or {}
            found.update({fmt: exporter for fmt, exporter in dict(extra).items()
                          if isinstance(fmt, str) and callable(exporter)})
        except Exception:
            logger.exception('Exporter resolver %r failed', resolver)
    return found


#: The order the export menus list the built-in formats in; the others
#: follow, by name.
FORMAT_ORDER = ('csv', 'xlsx', 'json', 'pdf')


def available_formats(request):
    """The export formats ``request`` may ask for: the ones the widgets list
    and the API takes. The built-in ones first (:data:`FORMAT_ORDER`), then
    the rest by name."""
    found = available_exporters(request)
    first = [fmt for fmt in FORMAT_ORDER if fmt in found]
    return first + sorted(fmt for fmt in found if fmt not in FORMAT_ORDER)


def export(source, request, params, fmt):
    """The response of exporting ``source`` with ``params`` as ``fmt``;
    ValidationError if ``request`` has no such format."""
    exporters = available_exporters(request)
    if not isinstance(fmt, str) or fmt not in exporters:
        raise ValidationError(_('Unknown export format: %s') % (fmt,))
    return exporters[fmt](source, request, params)


def export_handler():
    """The callable of ``GT_DATASOURCE_EXPORT_HANDLER`` (a callable or its
    dotted path), or None."""
    handler = getattr(settings, 'GT_DATASOURCE_EXPORT_HANDLER', None)
    if isinstance(handler, str):
        handler = import_string(handler) if handler else None
    return handler


def handle_export(source, request, params, fmt):
    """What the export endpoint answers: ``GT_DATASOURCE_EXPORT_HANDLER``
    gets the export first, as ``handler(request, source, params, fmt)``; a
    response from it is the answer (a background job, a redirect...), and
    ``None`` lets :func:`export` run as usual.

    The format and the parameters are checked before the handler sees them:
    the parameters with :func:`~djgentelella.datasources.query.validate_params`,
    so an unknown column or a wrong aggregate is a ValidationError (a 400 in
    the API) here and not an error of the background job the handler starts.
    :func:`export` itself never calls the handler, so a handler (or the job it
    starts) exports with it and does not come back to itself.
    """
    exporters = available_exporters(request)
    if not isinstance(fmt, str) or fmt not in exporters:
        raise ValidationError(_('Unknown export format: %s') % (fmt,))
    handler = export_handler()
    if handler is not None:
        errors = validate_params(source, request, params)[1]
        if errors:
            raise ValidationError([str(error) for error in errors])
        response = handler(request, source, params, fmt)
        if response is not None:
            return response
    return exporters[fmt](source, request, params)


def filename(source, ext):
    return '%s.%s' % (slugify(source.name.replace('.', '-')) or 'export', ext)


def attachment(response, source, ext):
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename(
        source, ext)
    return response


def export_limit():
    """Most rows the JSON and XLSX exports hold in memory
    (``GT_DATASOURCE_EXPORT_MAX_ROWS``, 50000 by default; None: no limit)."""
    return getattr(settings, 'GT_DATASOURCE_EXPORT_MAX_ROWS', 50000)


def limited(queryset, limit):
    """``(rows to export, truncated)``: at most ``limit`` rows of ``queryset``.
    ``truncated`` is computed without a COUNT, asking for one more row."""
    if limit is None:
        return queryset, False
    truncated = queryset[limit:limit + 1].exists()
    return queryset[:limit], truncated


def neutralize_formula(text):
    """``text`` with a leading ``'`` if a spreadsheet would run it as a
    formula (CSV injection)."""
    if text and text.startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


def iter_rows(source, request, queryset, columns, display=True, first=None):
    """Serialized rows, read ``CHUNK_SIZE`` at a time. ``first`` is the first
    chunk, already read (:func:`first_chunk`)."""
    start = 0
    while True:
        if first is not None:
            chunk, first = first, None
        else:
            chunk = serialize_rows(source, request,
                                   queryset[start:start + CHUNK_SIZE], columns,
                                   display=display)
        yield from chunk
        if len(chunk) < CHUNK_SIZE:
            return
        start += CHUNK_SIZE


def first_chunk(source, request, queryset, columns, display=True):
    """The first ``CHUNK_SIZE`` rows, read now: a streamed export reads them
    before it answers, so a source that cannot be read (a ValidationError, a
    :class:`~djgentelella.datasources.base.DataSourceUnavailable`) is an HTTP
    error and not a file cut after its header."""
    return serialize_rows(source, request, queryset[:CHUNK_SIZE], columns,
                          display=display)


def totals(source, request, params, queryset):
    """``[(column, fn, value)]`` for the ``aggregates`` of ``params``."""
    params = parse_params(params)
    if not params['aggregates']:
        return []
    colmap = source.column_map(request)
    exprs = {}
    specs = []
    for index, spec in enumerate(params['aggregates']):
        _key, expr = aggregate_expr(colmap, spec)
        exprs['_gt_t%d' % index] = expr
        specs.append(spec)
    values = queryset.order_by().aggregate(**exprs)
    return [(spec.get('column') or '', spec.get('fn'), values['_gt_t%d' % i])
            for i, spec in enumerate(specs)]


def totals_by_column(columns, total_list):
    """``{column name: "Sum: 10 · Average: 2"}`` for the footer of a table;
    a bare ``count`` goes under the first column."""
    footer = {}
    first = columns[0].name if columns else ''
    for name, fn, value in total_list:
        key = name if any(c.name == name for c in columns) else first
        text = '%s: %s' % (FUNCTION_LABELS.get(fn, fn), format_value(value))
        footer[key] = footer[key] + ' · ' + text if key in footer else text
    return footer


def format_value(value, column=None):
    """A cell as text, localized, for CSV and PDF."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return _('Yes') if value else _('No')
    if isinstance(value, datetime.datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return formats.date_format(value, 'SHORT_DATETIME_FORMAT')
    if isinstance(value, datetime.date):
        return formats.date_format(value, 'SHORT_DATE_FORMAT')
    if isinstance(value, float):
        return formats.number_format(round(value, 4))
    if isinstance(value, (Decimal, int)):
        return formats.number_format(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, cls=DjangoJSONEncoder)
    return str(value)


def _csv_value(value):
    if value is None:
        return ''
    if isinstance(value, datetime.datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return json.dumps(value, cls=DjangoJSONEncoder)
    if isinstance(value, str):
        # Numbers stay as they are: only text can carry a formula.
        return neutralize_formula(value)
    return str(value)


class _Echo:
    """A file-like object that hands back what is written: the csv module
    writes into it and the response streams each line."""

    def write(self, value):
        return value


@register_exporter('csv')
def export_csv(source, request, params):
    """Streams the rows as CSV, a header row of labels first.

    The first ``CHUNK_SIZE`` rows are read before the response is returned,
    so a source that fails to read is an HTTP error (400, or the 503 of
    :class:`~djgentelella.datasources.base.DataSourceUnavailable`) and not a
    file cut after its header. A failure after them (a later chunk) can only
    cut the stream; it is logged."""
    queryset = apply_params(source, request, params)
    columns = selected_columns(source, request, params)
    writer = csv.writer(_Echo())
    # Read before answering: an error here is a 400/503, not a cut file.
    first = first_chunk(source, request, queryset, columns)

    def lines():
        # A BOM, so a spreadsheet opens the file as UTF-8.
        yield '﻿'
        yield writer.writerow([str(c.label) for c in columns])
        try:
            for row in iter_rows(source, request, queryset, columns, first=first):
                yield writer.writerow([_csv_value(row[c.name]) for c in columns])
        except Exception:
            # The status is gone already: all that is left is to say why the
            # file is cut.
            logger.exception('CSV export of %s cut while streaming', source.name)
            raise

    response = StreamingHttpResponse(lines(), content_type='text/csv; charset=utf-8')
    return attachment(response, source, 'csv')


@register_exporter('json')
def export_json(source, request, params):
    """``{"source", "columns", "data", "aggregates"}``; the rows as the
    ``rows`` endpoint gives them (``fk`` as ``{"id", "display_name"}``)."""
    queryset = apply_params(source, request, params)
    columns = selected_columns(source, request, params)
    limit = export_limit()
    rows, truncated = limited(queryset, limit)
    data = list(iter_rows(source, request, rows, columns, display=False))
    body = {
        'source': source.name,
        'columns': [c.as_dict() for c in columns],
        'data': data,
        'truncated': truncated,
        'limit': limit,
        'aggregates': [{'column': name, 'fn': fn, 'value': value}
                       for name, fn, value in totals(source, request, params,
                                                     queryset)],
    }
    response = HttpResponse(json.dumps(body, cls=DjangoJSONEncoder),
                            content_type='application/json')
    return attachment(response, source, 'json')


# -- XLSX -------------------------------------------------------------------

def _xlsx_text(text):
    """``text`` without the control characters a sheet cannot hold."""
    return XLSX_ILLEGAL_CHARACTERS.sub('', text)


def _xlsx_value(value):
    if isinstance(value, datetime.datetime):
        if timezone.is_aware(value):
            value = timezone.make_naive(value)
        return value
    if isinstance(value, (dict, list)):
        value = json.dumps(value, cls=DjangoJSONEncoder)
    if isinstance(value, str):
        return _xlsx_text(value)
    return value


def _xlsx_text_cells(sheet, row_number):
    """Store as text the cells of a row that openpyxl took for formulas (a
    string that starts with ``=``): a value is never run as a formula."""
    for cell in sheet[row_number]:
        if cell.data_type == 'f':
            cell.data_type = 's'


def _excel_literal(column, value):
    """``value`` as an Excel formula literal, or None if it has none."""
    if value is None:
        return None
    if column.kind == 'boolean':
        return 'TRUE' if value else 'FALSE'
    if column.kind in ('integer', 'decimal'):
        return str(value)
    if column.kind == 'date':
        return 'DATE(%d,%d,%d)' % (value.year, value.month, value.day)
    if column.kind in ('string', 'text'):
        return '"%s"' % str(value).replace('"', '""')
    return None


#: Kinds whose cell holds the same value the filter compares with. ``fk`` and
#: ``choices`` cells hold their label and ``datetime`` cells a local time, so
#: their highlights are painted row by row instead.
_FORMULA_KINDS = ('string', 'text', 'integer', 'decimal', 'boolean', 'date')


def highlight_formula(column, cell, flt):
    """An Excel formula that is true when ``cell`` matches the filter ``flt``,
    or None when the filter has no formula form."""
    if column.kind not in _FORMULA_KINDS:
        return None
    op = flt.get('op', 'eq')
    value = flt.get('value')
    try:
        if op == 'isnull':
            return ('ISBLANK(%s)' if value in (None, True, 'true', 1)
                    else 'NOT(ISBLANK(%s))') % cell
        if op == 'in':
            items = [_excel_literal(column, coerce_value(column, v))
                     for v in (value or [])]
            if not items or None in items:
                return None
            return 'OR(%s)' % ','.join('%s=%s' % (cell, item) for item in items)
        if op == 'between':
            low, high = (_excel_literal(column, coerce_value(column, v))
                         for v in value)
            if low is None or high is None:
                return None
            return 'AND(%s>=%s,%s<=%s)' % (cell, low, cell, high)
        literal = _excel_literal(column, coerce_value(column, value))
    except (ValidationError, TypeError, ValueError):
        return None
    if literal is None:
        return None
    simple = {'eq': '=', 'ne': '<>', 'lt': '<', 'lte': '<=', 'gt': '>',
              'gte': '>='}
    if op in simple:
        return '%s%s%s' % (cell, simple[op], literal)
    if op == 'contains':
        return 'ISNUMBER(FIND(%s,%s))' % (literal, cell)
    if op == 'icontains':
        return 'ISNUMBER(SEARCH(%s,%s))' % (literal, cell)
    if op == 'startswith':
        return 'LEFT(%s,%d)=%s' % (cell, len(str(flt.get('value'))), literal)
    return None


def highlight_color(css):
    css = str(css or '')
    for name in css.split():
        if name in HIGHLIGHT_COLORS:
            return HIGHLIGHT_COLORS[name]
        match = HEX_COLOR.match(name)
        if match:
            return match.group(1).upper()
    return DEFAULT_HIGHLIGHT_COLOR


@register_exporter('xlsx')
def export_xlsx(source, request, params):
    """One sheet: header, rows, a totals row with the ``aggregates`` and the
    ``highlights`` as conditional formatting of the data range."""
    try:
        # Optional dependency: the `export` extra.
        from openpyxl import Workbook  # noqa: PLC0415
        from openpyxl.formatting.rule import FormulaRule  # noqa: PLC0415
        from openpyxl.styles import Font, PatternFill  # noqa: PLC0415
        from openpyxl.utils import get_column_letter  # noqa: PLC0415
    except ImportError:
        raise ImproperlyConfigured(
            'The xlsx export needs openpyxl: pip install "djgentelella[export]"')
    params = parse_params(params)
    queryset = apply_params(source, request, params)
    columns = selected_columns(source, request, params)
    colmap = source.column_map(request)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = (slugify(str(source.get_label())) or 'data')[:31]
    sheet.append([_xlsx_text(str(c.label)) for c in columns])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    sheet.freeze_panes = 'A2'

    pks = []
    rows, truncated = limited(queryset, export_limit())
    for row in iter_rows(source, request, rows, columns):
        pks.append(row['pk'])
        values = [_xlsx_value(row[c.name]) for c in columns]
        sheet.append(values)
        if any(isinstance(v, str) and v.startswith('=') for v in values):
            _xlsx_text_cells(sheet, sheet.max_row)
    last_row = len(pks) + 1
    last_col = get_column_letter(max(1, len(columns)))
    positions = {c.name: i + 1 for i, c in enumerate(columns)}

    static_rules = []
    for rule in params['highlights']:
        flt = rule.get('filter') if isinstance(rule, dict) else None
        if not isinstance(flt, dict):
            raise ValidationError(_('Each highlight needs a "filter" object.'))
        color = highlight_color(rule.get('css'))
        name = flt.get('column')
        formula = None
        if name in positions and name in colmap:
            cell = '$%s2' % get_column_letter(positions[name])
            formula = highlight_formula(colmap[name], cell, flt)
        if formula and pks:
            sheet.conditional_formatting.add(
                'A2:%s%d' % (last_col, last_row),
                FormulaRule(formula=[formula], stopIfTrue=False,
                            fill=PatternFill(start_color=color, end_color=color,
                                             fill_type='solid')))
        else:
            static_rules.append((rule, color))
    if static_rules and pks:
        index = {pk: i + 2 for i, pk in enumerate(pks)}
        for rule, color in static_rules:
            fill = PatternFill(start_color=color, end_color=color,
                               fill_type='solid')
            for pk in highlight_classes(source, request, queryset, pks, [rule],
                                        colmap):
                for cell in sheet[index[pk]]:
                    cell.fill = fill

    total_list = totals(source, request, params, queryset)
    if total_list:
        # One value under its column stays a number; several, or a bare
        # count, become text.
        cells = {}
        for name, fn, value in total_list:
            cells.setdefault(positions.get(name, 1), []).append(
                (name in positions, fn, value))
        for col, items in cells.items():
            cell = sheet.cell(row=last_row + 1, column=col)
            if len(items) == 1 and items[0][0]:
                cell.value = _xlsx_value(items[0][2])
            else:
                cell.value = _xlsx_text(' · '.join(
                    '%s: %s' % (FUNCTION_LABELS.get(fn, fn), format_value(value))
                    for _own, fn, value in items))
            cell.font = Font(bold=True)
    if truncated:
        note = sheet.cell(row=sheet.max_row + 2, column=1)
        note.value = _('Only the first %(limit)d rows are exported.') % {
            'limit': len(pks)}
        note.font = Font(italic=True)

    for i, column in enumerate(columns, start=1):
        sheet.column_dimensions[get_column_letter(i)].width = max(
            10, min(50, len(str(column.label)) + 4))

    out = BytesIO()
    workbook.save(out)
    response = HttpResponse(
        out.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.'
                     'spreadsheetml.sheet')
    return attachment(response, source, 'xlsx')


# -- PDF --------------------------------------------------------------------

#: Default template of the PDF export; a project overrides it like any other.
PDF_TEMPLATE = 'gentelella/datasources/export_pdf.html'


def pdf_context(source, request, params):
    """What the PDF template gets: the columns, the rows as text cells with
    their highlight color, the totals and a title."""
    params = parse_params(params)
    queryset = apply_params(source, request, params)
    columns = selected_columns(source, request, params)
    limit = getattr(settings, 'GT_DATASOURCE_PDF_MAX_ROWS', 5000)
    rows = list(iter_rows(source, request, queryset[:limit], columns))
    pks = [row['pk'] for row in rows]
    css = highlight_classes(source, request, queryset, pks, params['highlights'])
    total_list = totals(source, request, params, queryset)
    footer = totals_by_column(columns, total_list)
    return {
        'source': source,
        'title': str(source.get_label()),
        'columns': columns,
        'rows': [{
            'cells': [{'text': format_value(row[c.name], c),
                       'numeric': c.kind in ('integer', 'decimal')}
                      for c in columns],
            'color': highlight_color(css[row['pk']]) if row['pk'] in css else '',
        } for row in rows],
        'truncated': queryset.count() > limit,
        'limit': limit,
        'footer': [{'text': footer.get(c.name, ''),
                    'numeric': c.kind in ('integer', 'decimal')}
                   for c in columns] if footer else [],
        'generated_at': timezone.localtime() if settings.USE_TZ
        else datetime.datetime.now(),
        'params': params,
    }


def render_pdf(html):
    """PDF bytes of ``html`` with xhtml2pdf."""
    try:
        # Optional dependency: the `pdf` extra.
        from xhtml2pdf import pisa  # noqa: PLC0415
    except ImportError:
        raise ImproperlyConfigured(
            'The pdf export needs xhtml2pdf: pip install "djgentelella[pdf]"')
    out = BytesIO()
    result = pisa.CreatePDF(html, dest=out, encoding='utf-8')
    if result.err:
        raise RuntimeError('xhtml2pdf could not render the export (%d errors)'
                           % result.err)
    return out.getvalue()


@register_exporter('pdf')
def export_pdf(source, request, params):
    """The rows in ``PDF_TEMPLATE``: a table whose header repeats on every
    page, the totals and the page number in an ``@page`` frame."""
    html = render_to_string(PDF_TEMPLATE, pdf_context(source, request, params),
                            request=request)
    response = HttpResponse(render_pdf(html), content_type='application/pdf')
    return attachment(response, source, 'pdf')
