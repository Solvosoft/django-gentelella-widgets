"""Read-only tables over any data source.

Two components can show the rows of a data source that is not over a model
of the project -- one whose rows come from an external API, or are computed
in Python (:attr:`~djgentelella.datasources.base.DataSource.project_model`
is None):

* ``object_management`` in **list mode**: a ``datasource`` instead of
  ``model`` and ``form``. A DataTable with its search, its ordering, the
  facets of a panel and the row links (when the source is over a model of
  the project), and no create, update, detail or delete;
* ``interactive_grid`` over such a ``datasource``, which is read-only: no
  ``editable`` columns and no ``actions``.

Both read the rows through the node's endpoint (``gtapis/designs/<page>/
<node>/``), which applies the build: its columns (without those its
``column_conditions`` hide), its ``search_fields``, its ``ordering`` and its
``perms["list"]``, on top of the source's own ``has_permission`` and
``get_queryset``. The source stays readable through its own API
(``gtapis/datasources/<name>/``) by whoever has its permission: a column a
condition hides here is not a secret there.
"""

import json

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.utils.translation import gettext as _
from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from djgentelella.datasources import query
from djgentelella.datasources.base import (
    TEXT_KINDS, get_datasource, project_model_of,
)
from djgentelella.designs.conditions import check_conditions, hidden_columns
from djgentelella.permission_management import all_permission

__all__ = ['NOT_SHOWN', 'SourceGridViewSet', 'SourceTableViewSet', 'column_config',
           'resolve_source_list', 'source_rows']

#: Kinds of column a read-only table does not show.
NOT_SHOWN = ('json',)
#: The largest page each endpoint serves.
TABLE_MAX_PAGE = 1000
GRID_MAX_PAGE = 200


def column_config(column):
    """A column of a data source as the browser draws it (JSON-friendly)."""
    result = {'name': column.name, 'title': str(column.label), 'kind': column.kind}
    if column.choices is not None:
        result['choices'] = [[value, str(text)] for value, text in column.choices]
    return result


def resolve_source_list(rctx, path, props, build, *, names_prop,
                        default_ordering=()):
    """Resolve the read-only list of ``props["datasource"]`` into ``build``
    (an :class:`~djgentelella.designs.builds.ObjectManagementBuild`):
    ``datasource``, ``model`` (the source's project model, or None),
    ``title``, ``list_fields`` (from ``props[names_prop]``),
    ``search_fields``, ``ordering``, ``perms`` (only ``list``),
    ``source_columns`` and ``column_conditions``. Returns the source, or
    None after an error."""
    where = path + '.props.datasource'
    source = rctx.datasource(props['datasource'], where)
    if source is None:
        return None
    try:
        columns = source.column_map(rctx.request)
    except Exception:  # noqa: BLE001 -- a function source may need a request
        columns = None
    if columns is None:
        rctx.error(where, _('the columns of data source %r cannot be read')
                   % (props['datasource'],))
        return None
    shown = [name for name, column in columns.items() if column.kind not in NOT_SHOWN]
    names = props.get(names_prop) or shown[:6]
    names_path = '%s.props.%s' % (path, names_prop)
    if len(set(names)) != len(names):
        rctx.error(names_path, _('a column is listed twice'))
    for name in names:
        if name not in columns or columns[name].kind in NOT_SHOWN:
            rctx.error(names_path, _('%(column)r is not a column data source '
                                     '%(source)r can show') % {
                'column': name, 'source': props['datasource']})
    search = props.get('search_fields')
    if search is None:
        search = [name for name in names
                  if name in columns and columns[name].kind in TEXT_KINDS]
    for name in search:
        if name not in columns or columns[name].kind not in TEXT_KINDS:
            rctx.error(path + '.props.search_fields',
                       _('%(column)r is not a text column of data source '
                         '%(source)r') % {'column': name,
                                          'source': props['datasource']})
    ordering = props.get('ordering', list(default_ordering))
    for name in ordering:
        bare = str(name).lstrip('-')
        if bare != 'pk' and (bare not in columns or not columns[bare].sortable):
            rctx.error(path + '.props.ordering', _('unknown field %r') % (name,))
    perms = props.get('perms') or {}
    for action in perms:
        if action != 'list':
            rctx.error('%s.props.perms.%s' % (path, action),
                       _('a list over a data source only reads: it has no '
                         '%r permissions') % (action,))
    if perms.get('list'):
        rctx.check_permissions(path + '.props.perms.list', perms['list'])
    build.column_conditions = check_conditions(
        rctx, path + '.props.column_conditions', props.get('column_conditions'),
        list(names), _('column'))
    build.datasource = props['datasource']
    build.model = project_model_of(source)
    build.title = props.get('title') or str(source.get_label())
    build.list_fields = list(names)
    build.search_fields = list(search)
    build.ordering = list(ordering)
    build.perms = {'list': list(perms.get('list') or [])}
    build.source_columns = [column_config(columns[name]) for name in names
                            if name in columns]
    return source


def visible_columns(build, hidden):
    return [column for column in build.source_columns
            if column['name'] not in hidden]


def source_rows(build, source, request, queryset, columns):
    """The rows of ``queryset`` by column name, plus ``pk``: raw values, a
    relation as ``{id, display_name}`` (``serialize_rows``)."""
    colmap = source.column_map(request)
    return query.serialize_rows(source, request, queryset,
                                [colmap[name] for name in columns if name in colmap])


def _int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class SourceRowsMixin:
    """What both endpoints share: the build of the node
    (``request.gtdesign_build``), its permissions, the source and the
    columns the request sees."""

    authentication_classes = (SessionAuthentication,)
    permission_classes = (AllowAny,)
    renderer_classes = (JSONRenderer,)
    max_page = TABLE_MAX_PAGE

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.build = build = request.gtdesign_build
        if build.preview:
            raise Http404()
        needed = list(build.perms.get('list') or [])
        if needed and not all_permission(request.user, needed):
            raise PermissionDenied()
        try:
            self.source = get_datasource(build.datasource)
        except (KeyError, LookupError):
            raise Http404()
        if not self.source.has_permission(request):
            raise PermissionDenied()
        self.hidden = hidden_columns(build, request)
        self.columns = [column['name']
                        for column in visible_columns(build, self.hidden)]

    def page(self):
        data = self.request.query_params
        offset = max(0, _int(data.get('offset', data.get('start')), 0))
        limit = _int(data.get('limit', data.get('length')), 10)
        if limit < 0 or limit > self.max_page:
            limit = self.max_page
        return offset, limit

    def filters(self):
        """The filters of the facets (``?gtfilters=``): a list of C4 filters."""
        raw = self.request.query_params.get('gtfilters')
        if not raw:
            return []
        try:
            filters = json.loads(raw)
        except ValueError:
            raise ValidationError({'gtfilters': [_('not valid JSON')]})
        if not isinstance(filters, list) or not all(isinstance(item, dict)
                                                    for item in filters):
            raise ValidationError({'gtfilters': [_('must be a list of filters')]})
        return filters

    def asked_ordering(self):
        """``?ordering=`` (one column, ``-`` for descending) when the request
        sees it and it can be sorted; ``id`` is the pk. None: the build's."""
        item = (self.request.query_params.get('ordering') or '').strip()
        bare = item.lstrip('-')
        if bare == 'id':
            return [item[:len(item) - len(bare)] + 'pk']
        sortable = {column.name for column in self.source.columns(self.request)
                    if column.sortable}
        if bare and bare in self.columns and bare in sortable:
            return [item]
        return None

    def rows_queryset(self, filters=(), ordering=None):
        """The rows of the source with the search, ``filters`` and the
        ordering, only over the columns the request sees; 400 on a filter or
        an ordering by any other."""
        build, source, request = self.build, self.source, self.request
        search = (request.query_params.get('search') or '').strip()
        if ordering is None:
            ordering = [item for item in build.ordering
                        if str(item).lstrip('-') not in self.hidden]
        params = query.parse_params({'search': search, 'filters': list(filters),
                                     'ordering': list(ordering)})
        try:
            colmap = source.column_map(request)
            visible = {name: colmap[name] for name in self.columns if name in colmap}
            searched = {name: column for name, column in visible.items()
                        if name in build.search_fields}
            queryset = query.source_queryset(source, request, params)
            queryset = query.apply_filters(source, request, queryset,
                                           params['filters'], visible)
            queryset = query.apply_search(source, request, queryset,
                                          params['search'], searched)
            order = query.ordering_args(visible, [
                item for item in params['ordering'] if item.lstrip('-') != 'pk'])
            order += [item for item in params['ordering'] if item.lstrip('-') == 'pk']
        except DjangoValidationError as error:
            raise ValidationError({'detail': error.messages})
        if not any(item.lstrip('-') == 'pk' for item in order):
            order.append('pk')
        return queryset.order_by(*order)

    def total(self):
        return query.source_queryset(self.source, self.request, {}).count()


class SourceTableViewSet(SourceRowsMixin, viewsets.ViewSet):
    """The rows of ``object_management`` in list mode, as the DataTable of
    ``ObjectCRUD`` reads them: ``?offset=&limit=&draw=&search=&ordering=
    &gtfilters=`` -> ``{data, recordsTotal, recordsFiltered, draw}``, each row
    with its ``id`` and no ``actions``."""

    def list(self, request, *args, **kwargs):
        queryset = self.rows_queryset(self.filters(), self.asked_ordering())
        offset, limit = self.page()
        rows = source_rows(self.build, self.source, request,
                           queryset[offset:offset + limit], self.columns)
        for row in rows:
            row['id'] = row['pk']
            row['actions'] = {'detail': False, 'update': False, 'destroy': False}
        return Response({'data': rows, 'recordsTotal': self.total(),
                         'recordsFiltered': queryset.count(),
                         'draw': _int(request.query_params.get('draw'), 1)})


def _grid_value(value):
    """A relation as the grid draws it: ``{id, text}``."""
    if isinstance(value, dict) and 'display_name' in value:
        return {'id': value.get('id'), 'text': value['display_name']}
    if isinstance(value, list):
        return [_grid_value(item) for item in value]
    return value


class SourceGridViewSet(SourceRowsMixin, viewsets.ViewSet):
    """The rows of a read-only ``interactive_grid`` over a data source, as
    ``interactive_grid.js`` reads them: ``?limit=&offset=&search=`` ->
    ``{data, count}``, no row editable."""

    max_page = GRID_MAX_PAGE

    def list(self, request, *args, **kwargs):
        queryset = self.rows_queryset()
        offset, limit = self.page()
        rows = source_rows(self.build, self.source, request,
                           queryset[offset:offset + limit], self.columns)
        data = []
        for row in rows:
            item = {name: _grid_value(row.get(name)) for name in self.columns}
            item.update(id=row['pk'], actions={'update': False, 'destroy': False},
                        readonly=[])
            data.append(item)
        return Response({'data': data, 'count': queryset.count()})
