"""REST endpoints of the data sources, under ``gtapis/datasources/<name>/``.

=====================  ====================================================
``<name>/``            the source: its label and columns (what the widgets
                       build the table and the facets from)
``<name>/rows``        a page of rows in the DataTables format, so
                       ``gtCreateDataTable`` reads it unchanged
``<name>/aggregate``   ``query.aggregate``
``<name>/pivot``       ``query.pivot``
``<name>/facets``      ``query.facets`` of ``?columns=a,b``
``<name>/export``      ``export.export`` as ``?fmt=csv|xlsx|json|pdf``, or
                       ``GT_DATASOURCE_EXPORT_HANDLER``'s answer
=====================  ====================================================

The query parameters (the document of
:mod:`djgentelella.datasources.query`) travel as JSON: ``?params=<json>`` on a GET, or a
POST whose body is ``{"params": {...}}``, the parameter document itself, or a
form with a ``params`` field. Every endpoint checks the source's
``has_permission`` and answers 403 when it says no; bad parameters are a 400,
and a source that cannot read its rows now
(:class:`~djgentelella.datasources.base.DataSourceUnavailable`) a 503 -- or
the 502/504 it carries.
"""

import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import Http404
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .base import DataSourceUnavailable, get_datasource
from .export import available_formats, handle_export
from .query import (
    aggregate, apply_params, facets, highlight_classes, parse_params, pivot,
    selected_columns, serialize_rows, source_queryset,
)

#: The largest page the rows endpoint serves.
MAX_PAGE_SIZE = getattr(settings, 'GT_DATASOURCE_MAX_PAGE_SIZE', 1000)


#: Body keys that travel next to the parameters and are not part of them.
PAGING_KEYS = ('draw', 'offset', 'limit', 'start', 'length', 'fmt', 'facets')


def _int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class DataSourceView(APIView):
    """Base of the endpoints: finds the source, checks it may be read and
    reads the parameters."""

    def get_source(self, name):
        try:
            source = get_datasource(name)
        except KeyError:
            raise Http404(_('No data source %s') % name)
        if not source.has_permission(self.request):
            raise PermissionDenied()
        return source

    def get_params(self, request):
        data = request.query_params
        if request.method == 'POST':
            data = request.data
        raw = data.get('params') if hasattr(data, 'get') else None
        posted = request.method == 'POST' and isinstance(request.data, dict)
        if raw is None and posted:
            # The body is the parameter document itself, next to the paging
            # keys of the rows endpoint.
            raw = {k: v for k, v in request.data.items() if k not in PAGING_KEYS}
        if isinstance(raw, list):
            raw = raw[0] if raw else None
        params = parse_params(raw)
        # The keys gt_datatables' formatDataTableParams sends next to them.
        search = request.query_params.get('search')
        if search and not params['search']:
            params['search'] = search
        ordering = request.query_params.get('ordering')
        if ordering:
            params['ordering'] = [ordering] + [
                item for item in params['ordering']
                if item.lstrip('-') != ordering.lstrip('-')]
        return params

    def handle_exception(self, exc):
        # DataSourceUnavailable first: a source error that is both (a class
        # in transition, or one that carries ``messages``) is a 503, not a 400.
        if isinstance(exc, ValidationError) and \
                not isinstance(exc, DataSourceUnavailable):
            return Response({'detail': exc.messages},
                            status=status.HTTP_400_BAD_REQUEST)
        return super().handle_exception(exc)

    def get(self, request, name):
        source = self.get_source(name)
        return self.answer(request, source, self.get_params(request))

    def post(self, request, name):
        _body(request)
        return self.get(request, name)

    def answer(self, request, source, params):
        raise NotImplementedError


class DataSourceInfoView(DataSourceView):
    def get_params(self, request):
        return None

    def answer(self, request, source, params):
        return Response({
            'name': source.name,
            'label': str(source.get_label()),
            'columns': [c.as_dict() for c in source.columns(request)],
            'formats': sorted(available_formats(request)),
        })


class DataSourceRowsView(DataSourceView):
    def answer(self, request, source, params):
        data = request.data if request.method == 'POST' and hasattr(
            request.data, 'get') else request.query_params
        offset = max(0, _int(data.get('offset', data.get('start')), 0))
        limit = _int(data.get('limit', data.get('length')), 10)
        if limit < 0 or limit > MAX_PAGE_SIZE:
            limit = MAX_PAGE_SIZE
        queryset = apply_params(source, request, params)
        columns = selected_columns(source, request, params)
        rows = serialize_rows(source, request, queryset[offset:offset + limit],
                              columns)
        css = highlight_classes(source, request, queryset,
                                [row['pk'] for row in rows], params['highlights'])
        for row in rows:
            if row['pk'] in css:
                row['DT_RowClass'] = css[row['pk']]
        return Response({
            'data': rows,
            'recordsTotal': source_queryset(source, request, {}).count(),
            'recordsFiltered': queryset.count(),
            'draw': _int(data.get('draw'), 0),
        })


class DataSourceAggregateView(DataSourceView):
    def answer(self, request, source, params):
        return Response(aggregate(source, request, params))


class DataSourcePivotView(DataSourceView):
    def answer(self, request, source, params):
        return Response(pivot(source, request, params))


class DataSourceFacetsView(DataSourceView):
    def answer(self, request, source, params):
        # ?columns=a,b; in a POST body it is "facets", because "columns" is
        # the parameter that picks the columns of the rows.
        columns = request.query_params.get('columns')
        if columns is None and request.method == 'POST':
            columns = _body(request).get('facets')
        if isinstance(columns, str):
            columns = [name for name in columns.split(',') if name]
        if not columns:
            raise ValidationError(_('"columns" is required.'))
        return Response(facets(source, request, params, columns))


class DataSourceExportView(DataSourceView):
    def answer(self, request, source, params):
        fmt = request.query_params.get('fmt')
        if fmt is None and request.method == 'POST':
            fmt = _body(request).get('fmt')
        if fmt is not None and not isinstance(fmt, str):
            raise ValidationError(_('"fmt" has to be a string.'))
        return handle_export(source, request, params, fmt or 'csv')


def _body(request):
    """The POST body as a dict; any other JSON document is a bad request."""
    if not hasattr(request.data, 'get'):
        raise ValidationError(_('The body has to be a JSON object.'))
    return request.data


def params_json(params):
    """The parameter document as the ``params`` query string value."""
    return json.dumps(params or {}, separators=(',', ':'))
