"""The ``interactive_grid`` component: edit several rows of a table the way a
spreadsheet does, and save them together.

A grid shows ``columns`` of a model (or of a data source over a model) and
edits its ``editable`` ones in place, each cell with the djgentelella widget of
its field (:mod:`djgentelella.forms.widgetmap`, the same rules as a design's
``forms``). Rows can be added, marked for deletion and have their changes
undone in the browser; nothing is written until the user saves, and then
every change goes in one request to the node's ``save/`` endpoint::

    POST <endpoint>/save/
    {"rows": [
        {"key": "r1", "op": "update", "id": 5, "_version": "...",
         "data": {"price": "3.10"}},
        {"key": "n1", "op": "create", "data": {"name": "Pear", "price": "1.00"}},
        {"key": "r7", "op": "delete", "id": 7, "_version": "..."}
    ]}

The whole batch runs in one transaction, with the rows it touches locked
(``select_for_update``): either every row is saved or none is. Each row is
checked the way :mod:`djgentelella.locking` (C9) orders it -- permissions and
conditions (403), a row that does not exist (404), its version (409, or 428
without one), and last the validation of its data (400) -- and the answer
says what failed in each row.

The list (``GET <endpoint>/``) carries each row's ``_version``
(:attr:`~djgentelella.locking.OptimisticLockMixin.version_in_list`), what it
may do (``actions``) and which of its cells are read-only (``readonly``);
``GET <endpoint>/<pk>/`` reads one row again after a conflict.

Conditions (:mod:`djgentelella.designs.conditions`) work as in a table, plus
``edit_conditions``: a column whose condition does not hold is shown read-only.
A condition that names an authorization (``auth``) is evaluated with each row:
on ``update``/``destroy`` it decides whether that row can be changed or
deleted, on a column whether that cell can be edited.

See ``docs/source/designs.rst`` ("Interactive grid").
"""

from dataclasses import dataclass, field

from django.db import IntegrityError, connections, models, router, transaction
from django.db.models import signals
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.relations import PrimaryKeyRelatedField
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from djgentelella.authorization import evaluate_condition
from djgentelella.datasources.base import ModelDataSource, get_datasource
from djgentelella.designs import factories
from djgentelella.designs.builds import ObjectManagementBuild
from djgentelella.designs.components import Endpoint, RuntimeComponent
from djgentelella.designs.conditions import (
    about_object, check_conditions, conditions_schema, denied, hidden_columns,
    row_conditions, row_denied,
)
from djgentelella.designs.data_components import (
    OPTIMISTIC_LOCK_REQUIRED_SCHEMA, PERMISSION_LIST, allowed_fields, can,
    check_permissions, check_relation, columns_of, data_build, endpoint_url,
    json_config, kind_of, label, lock_props_errors, no_permission, plural,
    sample_rows,
)
from djgentelella.designs.forms import build_form, is_form_field, no_field
from djgentelella.designs.introspection import TEXT_KINDS
from djgentelella.forms import widgetmap
from djgentelella.locking import (
    VERSION_FIELD, OptimisticLockMixin, conflict_message, missing_message,
    object_version,
)
from djgentelella.permission_management import AllPermissionByAction, all_permission

__all__ = ['GRID_ACTIONS', 'GRID_COMPONENTS', 'GridState', 'InteractiveGridBuild',
           'InteractiveGridComponent', 'OPERATIONS', 'grid_viewset_for']

SCRIPT = 'gentelella/js/designs/interactive_grid.js'
TEMPLATE = 'gtdesigns/components/interactive_grid.html'
#: What a grid can do to its rows, and the model permission of each one.
GRID_ACTIONS = ('create', 'update', 'destroy')
GRID_PERMISSIONS = {'list': 'view', 'create': 'add', 'update': 'change',
                    'destroy': 'delete'}
#: ``op`` of a row of a batch -> the action it is.
OPERATIONS = {'create': 'create', 'update': 'update', 'delete': 'destroy'}
#: Kinds of field a grid cannot show.
NOT_SHOWN = ('json', 'binary', 'point', 'other', 'file', 'image')
#: Kinds of field a cell cannot edit: their widgets need room or an upload.
NOT_EDITABLE = NOT_SHOWN + ('auto', 'm2m')
#: The most rows one save may carry.
MAX_BATCH_ROWS = 500
#: The precedence of the failures of a batch, as C9 orders them: the answer
#: has the status of the first one found here.
STATUS_ORDER = (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND,
                status.HTTP_409_CONFLICT, status.HTTP_428_PRECONDITION_REQUIRED,
                status.HTTP_400_BAD_REQUEST)


@dataclass
class InteractiveGridBuild(ObjectManagementBuild):
    """A grid over the rows of ``model``: ``list_fields`` are its columns."""

    #: Name of a :class:`~djgentelella.datasources.base.ModelDataSource` the
    #: rows come from (its queryset, permissions and Site rule), or ``''``.
    datasource: str = ''
    #: The columns a cell can edit; ``form`` is the GTForm of them.
    editable: list = field(default_factory=list)
    #: ``{column: condition}``: editable only where it holds.
    edit_conditions: dict = field(default_factory=dict)
    #: Which of :data:`GRID_ACTIONS` the grid offers.
    actions: list = field(default_factory=lambda: list(GRID_ACTIONS))
    page_size: int = 25
    #: Versions are checked on every update and delete of a batch.
    optimistic_lock: bool = True
    #: Its conditions on one row (:func:`~djgentelella.designs.conditions.
    #: row_conditions`). A class attribute, not a field.
    row_actions = ('update', 'destroy')


# -- conditions and permissions for one request -------------------------------------

class GridState:
    """What one request may see and do in a grid: evaluated once, and per row
    only for the conditions that name the row (``auth``)."""

    def __init__(self, build, request):
        self.build = build
        self.request = request
        self.hidden = hidden_columns(build, request) if build.column_conditions \
            else set()
        refused = denied(build, request) if build.action_conditions else set()
        user = request.user
        self.allowed = {name: (name in build.actions and name not in refused
                               and all_permission(user, list(build.perms[name])))
                        for name in GRID_ACTIONS}
        self.per_row = bool(row_conditions(build))
        once, self.edit_per_row = {}, {}
        for name, cond in (build.edit_conditions or {}).items():
            (self.edit_per_row if about_object(cond) else once)[name] = cond
        #: Editable columns no cell of this request can edit.
        self.readonly = {name for name, cond in once.items()
                         if not evaluate_condition(cond, request, None)}
        self.editable = [name for name in build.editable
                         if name not in self.hidden and name not in self.readonly]

    def row_actions(self, obj):
        """``{'update': bool, 'destroy': bool}`` on the row ``obj``."""
        refused = row_denied(self.build, self.request, obj) if self.per_row else ()
        return {name: self.allowed[name] and name not in refused
                for name in ('update', 'destroy')}

    def row_readonly(self, obj):
        """The editable columns whose condition does not hold on ``obj``
        (``None`` for a new row)."""
        return {name for name, cond in self.edit_per_row.items()
                if name in self.editable
                and not evaluate_condition(cond, self.request, obj)}


# -- the component ------------------------------------------------------------------

def overrides(model, name):
    """Whether ``model`` has its own ``save``/``delete``."""
    return getattr(model, name) is not getattr(models.Model, name)


def required_fields(model):
    """The fields a new row of ``model`` cannot do without."""
    return [model_field.name for model_field in model._meta.concrete_fields
            if is_form_field(model_field) and not model_field.blank
            and not model_field.has_default() and not model_field.primary_key]


class InteractiveGridComponent(RuntimeComponent):
    """Rows of a model edited in place, saved together in one transaction."""

    type = 'interactive_grid'
    label = gettext_lazy('Interactive grid (edit rows in place)')
    icon = 'fa fa-th'
    props_schema = {
        'type': 'object',
        'required': ['columns'],
        'additionalProperties': False,
        'properties': {
            'model': {'type': 'string', 'x-widget': 'model', 'title': 'Model'},
            'datasource': {'type': 'string', 'x-widget': 'datasource',
                           'title': 'Data source over a model (instead of a model)'},
            'title': {'type': 'string', 'title': 'Title'},
            'columns': {'type': 'array', 'items': {'type': 'string'},
                        'minItems': 1, 'x-widget': 'model-fields',
                        'title': 'Columns'},
            'editable': {'type': 'array', 'items': {'type': 'string'},
                         'x-widget': 'model-fields',
                         'title': 'Editable columns (default: every column '
                                  'a cell can edit)'},
            'widgets': {'type': 'object', 'additionalProperties': {'type': 'string'},
                        'x-widget': 'widgets',
                        'title': 'Widget of an editable column'},
            'search_fields': {'type': 'array', 'items': {'type': 'string'},
                              'x-widget': 'model-text-fields',
                              'title': 'Searched by the search box'},
            'ordering': {'type': 'array', 'items': {'type': 'string'},
                         'title': 'Ordering (default: pk)'},
            'actions': {'type': 'array', 'items': {'enum': list(GRID_ACTIONS)},
                        'title': 'What it can do (default: %s)'
                                 % ', '.join(GRID_ACTIONS)},
            'perms': {
                'type': 'object',
                'x-widget': 'perms',
                'title': 'Permissions per action (empty = the model ones)',
                'additionalProperties': False,
                'properties': {name: PERMISSION_LIST for name in GRID_PERMISSIONS},
            },
            'column_conditions': conditions_schema(
                'Columns shown only when (by field)'),
            'edit_conditions': conditions_schema(
                'Columns editable only when (by field)'),
            'action_conditions': conditions_schema(
                'Actions allowed only when', list(GRID_ACTIONS)),
            'optimistic_lock': {
                'type': 'boolean', 'default': True,
                'title': 'Refuse to save a row somebody else changed after it '
                         'was read (optimistic locking)'},
            'optimistic_lock_required': OPTIMISTIC_LOCK_REQUIRED_SCHEMA,
            'page_size': {'type': 'integer', 'minimum': 1, 'maximum': 200,
                          'title': 'Rows per page (default 25)'},
        },
    }

    def resolve(self, node, rctx, path):
        props = node.get('props') or {}
        build = data_build(InteractiveGridBuild, node, rctx,
                           page_size=props.get('page_size', 25))
        found, source = self.resolve_model(props, rctx, path, build)
        if found is None:
            return build
        model = found.model
        model_label = found.model._meta.label
        by_name = allowed_fields(found)
        # Over a data source, only the columns it offers.
        offered = set(source.field_names()) if source is not None else None

        columns = props['columns']
        where = path + '.props.columns'
        if len(set(columns)) != len(columns):
            rctx.error(where, _('a column is listed twice'))
        for name in columns:
            if name not in by_name or (offered is not None and name not in offered):
                rctx.error(where, no_field(model_label, name))
            elif kind_of(by_name[name]) in NOT_SHOWN or by_name[name].primary_key:
                rctx.error(where, _('%r cannot be a grid column') % (name,))
            else:
                check_relation(rctx, where, by_name[name])

        def can_edit(name):
            return name in by_name and is_form_field(by_name[name]) \
                and kind_of(by_name[name]) not in NOT_EDITABLE

        editable = props.get('editable')
        if editable is None:
            editable = [name for name in columns if can_edit(name)]
        where = path + '.props.editable'
        for name in editable:
            if name not in columns:
                rctx.error(where, _('%r is not one of the columns') % (name,))
            elif name in by_name and not can_edit(name):
                rctx.error(where, _('%r cannot be edited in a grid') % (name,))
        if len(set(editable)) != len(editable):
            rctx.error(where, _('a column is listed twice'))
        widgets = props.get('widgets') or {}
        for name in widgets:
            if name not in editable:
                rctx.error(path + '.props.widgets',
                           _('%r is not an editable column') % (name,))

        search = props.get('search_fields')
        if search is None:
            search = [name for name in columns if name in by_name
                      and kind_of(by_name[name]) in TEXT_KINDS]
        for name in search:
            if name not in by_name or kind_of(by_name[name]) not in TEXT_KINDS:
                rctx.error(path + '.props.search_fields',
                           _('%(field)r is not a text field of %(model)s') % {
                               'field': name, 'model': model_label})
        ordering = props.get('ordering', ['pk'])
        for name in ordering:
            bare = name.lstrip('-')
            if bare not in set(by_name) | {'pk'} or \
                    (bare in by_name and kind_of(by_name[bare]) == 'm2m'):
                rctx.error(path + '.props.ordering', _('unknown field %r') % (name,))

        actions = list(dict.fromkeys(props.get('actions', GRID_ACTIONS)))
        if 'create' in actions:
            missing = [name for name in required_fields(model)
                       if name not in editable]
            if missing:
                rctx.error(path + '.props.actions',
                           _('adding rows needs every required field editable: '
                             'add %s to "editable", or leave "create" out of '
                             '"actions"') % ', '.join(missing))
        perms = {name: found.permissions(permission)
                 for name, permission in GRID_PERMISSIONS.items()}
        perms.update(props.get('perms', {}))
        for name, needed in perms.items():
            check_permissions(rctx, path + '.props.perms.' + name, needed)
        if model._meta.pk.name != 'id' and 'id' in by_name:
            rctx.error(path + '.props.model', _('%s has a field "id" that is not '
                                                'its primary key: the grid needs '
                                                '"id" for the row') % model_label)
        column_conditions = check_conditions(
            rctx, path + '.props.column_conditions', props.get('column_conditions'),
            list(columns), _('column'))
        edit_conditions = check_conditions(
            rctx, path + '.props.edit_conditions', props.get('edit_conditions'),
            list(editable), _('editable column'))
        action_conditions = check_conditions(
            rctx, path + '.props.action_conditions', props.get('action_conditions'),
            list(GRID_ACTIONS), _('action'))
        if rctx.has_errors_under(path):
            return build
        form = build_form('%s_grid' % node['id'],
                          {'model': model_label, 'fields': list(editable),
                           'widgets': widgets}, rctx, path + '.props')
        if form is None:
            return build

        build.title = props.get('title') or plural(model)
        build.model = model
        build.form = form
        build.list_fields = list(columns)
        build.editable = list(editable)
        build.search_fields = list(search)
        build.ordering = list(ordering)
        build.actions = actions
        build.perms = perms
        build.columns = columns_of(found)
        build.column_conditions = column_conditions
        build.edit_conditions = edit_conditions
        build.action_conditions = action_conditions
        build.optimistic_lock = bool(props.get('optimistic_lock', True))
        # With locking a grid always requires the version of each row it
        # saves (428 without it): the prop only states it.
        build.optimistic_lock_required = build.optimistic_lock and bool(
            props.get('optimistic_lock_required', False))
        return build

    def check_props(self, node, path):
        errors = super().check_props(node, path)
        return errors or lock_props_errors(node.get('props') or {}, path,
                                           lock_default=True)

    def resolve_model(self, props, rctx, path, build):
        """``(exposure, data source)`` of the grid: of its ``model``, or of the
        model of its ``datasource``, which must be over one. ``(None, None)``
        after an error."""
        has_model, has_source = bool(props.get('model')), bool(props.get('datasource'))
        if has_model == has_source:
            rctx.error(path + '.props', _('give a "model" or a "datasource", not both'))
            return None, None
        if has_model:
            return rctx.exposure(props['model'], path + '.props.model'), None
        where = path + '.props.datasource'
        source = rctx.datasource(props['datasource'], where)
        if source is None:
            return None, None
        if not isinstance(source, ModelDataSource) or source.model is None:
            rctx.error(where, _('data source %r is not over a model: a grid edits '
                                'the rows of a model') % (props['datasource'],))
            return None, None
        build.datasource = props['datasource']
        return rctx.exposure(source.model._meta.label, where), source

    # -- page ---------------------------------------------------------------------

    def render(self, build, rctx, children):
        if build.model is None:
            return mark_safe('')
        if rctx.preview:
            return render_to_string(TEMPLATE, {
                'b': build, 'preview': True,
                'columns': [label(build.model._meta.get_field(name).verbose_name)
                            for name in build.list_fields],
                'rows': sample_rows(build.model, build.list_fields)})
        if not can(rctx, build.perms['list']):
            return no_permission(build)
        if build.datasource and not source_allows(build, rctx.request):
            return no_permission(build)
        base = endpoint_url(rctx, build)
        if base is None:
            return no_permission(build)
        state = GridState(build, rctx.request)
        writes = state.allowed['create'] or state.allowed['update']
        cells = []
        if writes and state.editable:
            form = build.form.get_form(prefix='%s-__row__' % build.id)
            cells = [(name, form[name]) for name in state.editable]
        config = {
            'id': build.id,
            'prefix': build.id,
            'url': base,
            'page_size': build.page_size,
            'search': bool(build.search_fields),
            'lock': build.optimistic_lock,
            'allowed': state.allowed,
            'columns': grid_columns(build, state),
        }
        return render_to_string(TEMPLATE, {
            'b': build, 'cells': cells, 'allowed': state.allowed,
            'config': json_config(build.id + '_gtconfig', config),
        }, request=rctx.request)

    def media(self, build, rctx):
        return {'js': [SCRIPT]}

    def endpoints(self, build):
        if build.model is None:
            return []
        return [Endpoint('', grid_viewset_for(build), 'gtdesign-%s' % build.id)]


def source_allows(build, request):
    try:
        source = get_datasource(build.datasource)
    except (KeyError, LookupError):
        return False
    return source.has_permission(request)


def grid_columns(build, state):
    """The columns of the page: those the request sees, as JSON-friendly data
    (the browser writes them as text, never as HTML)."""
    widgets = {form_field.name: form_field.widget for form_field in build.form.fields}
    result = []
    for name in build.list_fields:
        if name in state.hidden:
            continue
        model_field = build.model._meta.get_field(name)
        kind = kind_of(model_field)
        column = {'name': name, 'title': label(model_field.verbose_name),
                  'kind': kind, 'editable': name in state.editable}
        if name in widgets:
            column['widget'] = widgets[name]
            column['lookup'] = widgets[name] in widgetmap.LOOKUP_WIDGETS
        if kind == 'choices':
            column['choices'] = [[value, str(text)]
                                 for value, text in model_field.flatchoices]
        result.append(column)
    return result


# -- serializers --------------------------------------------------------------------

class BatchPrimaryKeyRelatedField(PrimaryKeyRelatedField):
    """A ``PrimaryKeyRelatedField`` that finds its object among those the
    batch read beforehand (one query per relation, not per row)."""

    def to_internal_value(self, data):
        cache = (self.root.context.get('gtgrid_related') or {}).get(self.field_name)
        if cache and not isinstance(data, bool):
            found = cache.get(str(data))
            if found is not None:
                return found
        return super().to_internal_value(data)


def _row_serializer(build):
    model = build.model
    attrs = {'__module__': factories.__name__}
    for name in build.list_fields:
        declared = factories._list_field(model._meta.get_field(name))
        if declared is not None:
            attrs[name] = declared

    def get_actions(self, obj):
        return self.context['gtgrid_state'].row_actions(obj)

    def get_readonly(self, obj):
        return sorted(self.context['gtgrid_state'].row_readonly(obj))

    attrs.update(actions=serializers.SerializerMethodField(), get_actions=get_actions,
                 readonly=serializers.SerializerMethodField(),
                 get_readonly=get_readonly)
    if model._meta.pk.name != 'id':
        attrs['id'] = serializers.ReadOnlyField(source='pk')
    attrs['Meta'] = type('Meta', (), {
        'model': model, 'fields': ['id'] + build.list_fields + ['actions', 'readonly']})
    return type(factories.class_name(build, 'GridRowSerializer'),
                (serializers.ModelSerializer,), attrs)


def _write_serializer(build):
    model = build.model
    attrs = {'__module__': factories.__name__,
             'serializer_related_field': BatchPrimaryKeyRelatedField}
    for name in build.editable:
        declared = factories._write_field(model._meta.get_field(name), False)
        if declared is not None:
            attrs[name] = declared
    attrs['Meta'] = type('Meta', (), {'model': model, 'fields': list(build.editable)})
    return type(factories.class_name(build, 'GridWriteSerializer'),
                (serializers.ModelSerializer,), attrs)


def _table_serializer(build):
    row = row_serializer_for(build)
    return type(factories.class_name(build, 'GridTableSerializer'),
                (serializers.Serializer,), {
                    '__module__': factories.__name__,
                    'data': serializers.ListField(child=row(), required=True),
                    'count': serializers.IntegerField(required=True)})


def row_serializer_for(build):
    """A row of the grid: its columns (relations as ``{id, text}``) and what
    the request may do on it (``actions``, ``readonly``)."""
    return factories.cached(build, 'grid-row', _row_serializer)


def write_serializer_for(build):
    """What a row of a batch writes: the editable columns."""
    return factories.cached(build, 'grid-write', _write_serializer)


# -- the batch ----------------------------------------------------------------------

class BatchRow:
    """One row of a batch, as parsed, and what became of it."""

    def __init__(self, index, key, op, pk=None, version=None, data=None):
        self.index = index
        self.key = key
        self.op = op
        self.action = OPERATIONS[op]
        self.pk = pk
        self.version = version
        self.data = data or {}
        self.pk_value = None
        self.instance = None
        self.serializer = None
        self.failure = None
        #: Field errors found before the validation, reported with it (400
        #: is the last of the checks).
        self.field_errors = {}

    def fail(self, status_code, code, detail=None, **extra):
        self.failure = {'key': self.key, 'op': self.op, 'status': status_code,
                        'code': code, **extra}
        if self.pk is not None:
            self.failure['id'] = self.pk
        if detail is not None:
            self.failure['detail'] = str(detail)


class BatchError(Exception):
    """A body that is not a batch: the answer is a 400, nothing per row."""


def parse_batch(data, limit=MAX_BATCH_ROWS):
    """The :class:`BatchRow` list of the body of a save."""
    rows = data.get('rows') if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise BatchError(_('The body must be {"rows": [...]}, with at least one row.'))
    if len(rows) > limit:
        raise BatchError(_('Too many rows: at most %d in one save.') % limit)
    result, keys, ids = [], set(), set()
    for index, item in enumerate(rows):
        if not isinstance(item, dict):
            raise BatchError(_('Row %d is not an object.') % index)
        key = item.get('key', index)
        op = item.get('op')
        if not isinstance(key, (str, int)) or isinstance(key, bool) or key == '':
            raise BatchError(_('Row %d has no valid "key".') % index)
        key = str(key)
        if key in keys:
            raise BatchError(_('The key %r is used twice.') % key)
        keys.add(key)
        if op not in OPERATIONS:
            raise BatchError(_('Row %(row)s: "op" must be one of %(ops)s.') % {
                'row': key, 'ops': ', '.join(OPERATIONS)})
        pk = item.get('id')
        if op == 'create':
            if pk is not None:
                raise BatchError(_('Row %s: a new row has no "id".') % key)
        elif not isinstance(pk, (str, int)) or isinstance(pk, bool) or pk == '':
            raise BatchError(_('Row %s needs the "id" of the row.') % key)
        elif str(pk) in ids:
            raise BatchError(_('The row %s appears twice.') % pk)
        else:
            ids.add(str(pk))
        values = item.get('data', {})
        if op == 'delete':
            values = {}
        elif not isinstance(values, dict):
            raise BatchError(_('Row %s: "data" must be an object.') % key)
        version = item.get(VERSION_FIELD)
        version = None if version in (None, '') else str(version)
        result.append(BatchRow(index, key, op, pk, version, values))
    return result


def denied_message(row_action):
    return {'create': _('You cannot add rows here.'),
            'update': _('You cannot change this row.'),
            'destroy': _('You cannot delete this row.')}[row_action]


class Batch:
    """The save of a batch by a grid viewset: check every row, and write
    them all only when none failed. Call :meth:`run` inside one
    ``transaction.atomic()``."""

    def __init__(self, view, state, rows):
        self.view = view
        self.state = state
        self.build = view.gtdesign_build
        self.model = self.build.model
        self.rows = rows
        self.using = router.db_for_write(self.model)
        self.error = None

    @property
    def failed(self):
        return [row for row in self.rows if row.failure is not None]

    def run(self):
        """Whether every row was saved."""
        self.check_actions()
        self.check_rows(self.read_rows())
        self.validate()
        if self.failed:
            return False
        try:
            with transaction.atomic(using=self.using):
                self.write()
        except IntegrityError:
            self.error = _('The database refused the rows (a duplicate value?). '
                           'Nothing was saved.')
            return False
        return True

    # 403 before anything else, per row: the action, then the columns.
    def check_actions(self):
        state = self.state
        for row in self.rows:
            if not state.allowed[row.action]:
                row.fail(403, 'permission_denied', denied_message(row.action))
                continue
            names = set(row.data)
            forbidden = names & (state.hidden | state.readonly)
            if forbidden:
                row.fail(403, 'permission_denied',
                         _('You cannot change these columns: %s.') % ', '.join(
                             sorted(forbidden)), fields=sorted(forbidden))
                continue
            for name in sorted(names - set(state.editable)):
                row.field_errors[name] = [_('This column cannot be edited here.')]

    def read_rows(self):
        """``{pk: object}`` of the rows to update or delete, locked, read in
        one query; only those the grid reaches (its data source, if any)."""
        model_pk = self.model._meta.pk
        wanted = []
        for row in self.rows:
            if row.op == 'create' or row.failure is not None:
                continue
            if factories.valid_pk(self.model, row.pk):
                row.pk_value = model_pk.to_python(row.pk)
                wanted.append(row.pk_value)
        if not wanted:
            return {}
        queryset = self.view.get_queryset().select_related(None) \
            .prefetch_related(None).filter(pk__in=wanted).order_by('pk')
        if connections[self.using].in_atomic_block:
            queryset = queryset.select_for_update()
        return {obj.pk: obj for obj in queryset}

    # Then, on each existing row: 404, its conditions (403), its version.
    def check_rows(self, objects):
        state = self.state
        for row in self.rows:
            if row.failure is not None:
                continue
            if row.op == 'create':
                readonly = set(row.data) & state.row_readonly(None)
                if readonly:
                    row.fail(403, 'permission_denied',
                             _('You cannot change these columns: %s.') % ', '.join(
                                 sorted(readonly)), fields=sorted(readonly))
                continue
            obj = objects.get(row.pk_value)
            if obj is None:
                row.fail(404, 'not_found', _('This row no longer exists, or you can '
                                             'no longer reach it.'))
                continue
            row.instance = obj
            if not state.row_actions(obj)[row.action]:
                row.fail(403, 'permission_denied', denied_message(row.action))
                continue
            readonly = set(row.data) & state.row_readonly(obj)
            if readonly:
                row.fail(403, 'permission_denied',
                         _('You cannot change these columns: %s.') % ', '.join(
                             sorted(readonly)), fields=sorted(readonly))
                continue
            if self.build.optimistic_lock:
                current = object_version(obj)
                if row.version is None:
                    row.fail(428, 'version_required', missing_message())
                elif row.version != current:
                    row.fail(409, 'version_conflict', conflict_message(obj),
                             version=current)

    # Last, the data (400).
    def validate(self):
        writes = [row for row in self.rows
                  if row.failure is None and row.op != 'delete']
        if not writes:
            return
        serializer_class = write_serializer_for(self.build)
        context = self.view.get_serializer_context()
        context['gtgrid_related'] = self.read_related(serializer_class, writes)
        for row in writes:
            data = {name: value for name, value in row.data.items()
                    if name not in row.field_errors}
            row.serializer = serializer_class(
                row.instance, data=data, partial=row.op == 'update', context=context)
            errors = {} if row.serializer.is_valid() else dict(row.serializer.errors)
            errors.update(row.field_errors)
            if errors:
                row.fail(400, 'invalid', _('This row has errors.'), errors=errors)

    def read_related(self, serializer_class, writes):
        """``{field: {str(pk): object}}`` of the relations the rows name,
        one query per relation field."""
        result = {}
        for name, item in serializer_class().fields.items():
            if not isinstance(item, BatchPrimaryKeyRelatedField):
                continue
            related = item.get_queryset().model
            values = {row.data[name] for row in writes
                      if isinstance(row.data.get(name), (str, int))
                      and not isinstance(row.data.get(name), bool)
                      and factories.valid_pk(related, row.data[name])}
            if values:
                result[name] = {str(obj.pk): obj for obj in
                                item.get_queryset().filter(pk__in=values)}
        return result

    def bulk_safe(self):
        """Whether the rows can be written without ``save()``: the model has
        none of its own and nothing listens to its signals."""
        model = self.model
        return not overrides(model, 'save') and not (
            signals.pre_save.has_listeners(model)
            or signals.post_save.has_listeners(model))

    def write(self):
        model = self.model
        manager = model._base_manager.db_manager(self.using)
        deleted = [row.instance for row in self.rows if row.op == 'delete']
        if deleted:
            if overrides(model, 'delete'):
                for obj in deleted:
                    obj.delete()
            else:
                manager.filter(pk__in=[obj.pk for obj in deleted]).delete()
        updates = [row for row in self.rows if row.op == 'update'
                   and row.serializer.validated_data]
        creates = [row for row in self.rows if row.op == 'create']
        bulk = self.bulk_safe()
        if updates and bulk:
            names = set()
            for row in updates:
                for name, value in row.serializer.validated_data.items():
                    setattr(row.instance, name, value)
                    names.add(name)
            # What save() would have done: auto_now fields (a version field
            # among them, GTLockMeta) get the time of the save.
            for model_field in model._meta.concrete_fields:
                if getattr(model_field, 'auto_now', False):
                    names.add(model_field.name)
                    for row in updates:
                        model_field.pre_save(row.instance, False)
            manager.bulk_update([row.instance for row in updates], sorted(names))
        else:
            for row in updates:
                row.serializer.save()
        if creates and bulk and not model._meta.parents and \
                connections[self.using].features.can_return_rows_from_bulk_insert:
            objects = manager.bulk_create([
                model(**row.serializer.validated_data) for row in creates])
            for row, obj in zip(creates, objects):
                row.instance = obj
        else:
            for row in creates:
                row.instance = row.serializer.save()

    def response(self):
        if self.error is not None:
            return Response({'saved': False, 'code': 'batch_rejected',
                             'detail': self.error, 'rows': []},
                            status=status.HTTP_400_BAD_REQUEST)
        failed = self.failed
        if failed:
            found = {row.failure['status'] for row in failed}
            code = next(item for item in STATUS_ORDER if item in found)
            return Response({
                'saved': False, 'code': 'batch_rejected',
                'detail': _('Nothing was saved: %(failed)d of %(total)d rows have '
                            'problems.') % {'failed': len(failed),
                                            'total': len(self.rows)},
                'rows': [row.failure for row in failed]}, status=code)
        saved = [row.instance.pk for row in self.rows if row.op != 'delete']
        fresh = {}
        if saved:
            fresh = {obj.pk: obj for obj in
                     self.view.get_queryset().filter(pk__in=saved)}
        serializer = self.view.row_serializer()
        rows = []
        for row in self.rows:
            item = {'key': row.key, 'op': row.op}
            if row.op == 'delete':
                item['id'] = row.pk
            else:
                item['id'] = row.instance.pk
                obj = fresh.get(row.instance.pk)
                item['row'] = self.view.represent(serializer, obj) \
                    if obj is not None else None
            rows.append(item)
        return Response({'saved': True, 'rows': rows})


# -- the viewset --------------------------------------------------------------------

class GridMixin:
    """The API of a grid: ``list``, ``retrieve`` (one row, to reload it) and
    ``save`` (a batch). Goes before ``ManagementMixin``, whose conditions,
    hidden columns and filters it shares with the tables."""

    max_batch_rows = MAX_BATCH_ROWS
    version_in_list = True

    def grid_state(self):
        if not hasattr(self, '_gtgrid_state'):
            self._gtgrid_state = GridState(self.gtdesign_build, self.request)
        return self._gtgrid_state

    def get_serializer_class(self):
        if self.action == 'list':
            return self.gtgrid_table_serializer
        return self.serializer_class

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['gtgrid_state'] = self.grid_state()
        return context

    def get_queryset(self):
        build = self.gtdesign_build
        queryset = self.queryset.all()
        if build.datasource:
            try:
                source = get_datasource(build.datasource)
            except (KeyError, LookupError):
                raise PermissionDenied()
            if not source.has_permission(self.request):
                raise PermissionDenied()
            queryset = queryset.filter(
                pk__in=source.get_queryset(self.request).values('pk'))
        if build.preview:
            return queryset.none()
        return queryset

    def row_serializer(self):
        serializer = self.serializer_class(context=self.get_serializer_context())
        for name in self.gtdesign_hidden:
            serializer.fields.pop(name, None)
        return serializer

    def represent(self, serializer, obj):
        data = serializer.to_representation(obj)
        data[VERSION_FIELD] = object_version(obj)
        return data

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is None:
            page = list(queryset)
            count = len(page)
        else:
            count = self.paginator.count
        return Response(self.get_serializer({'data': page, 'count': count}).data)

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        return Response(self.represent(self.row_serializer(), obj))

    @action(detail=False, methods=['post'])
    def save(self, request, *args, **kwargs):
        try:
            rows = parse_batch(request.data, self.max_batch_rows)
        except BatchError as error:
            return Response({'saved': False, 'code': 'invalid_batch',
                             'detail': str(error), 'rows': []},
                            status=status.HTTP_400_BAD_REQUEST)
        batch = Batch(self, self.grid_state(), rows)
        with transaction.atomic(using=batch.using):
            if not batch.run():
                transaction.set_rollback(True, using=batch.using)
        return batch.response()


class GridPagination(LimitOffsetPagination):
    default_limit = 25
    max_limit = 200


def _grid_viewset(build):
    model = build.model
    kinds = {name: kind_of(model._meta.get_field(name)) for name in build.list_fields}
    names = build.list_fields
    queryset = model._default_manager.select_related(
        *[name for name in names if kinds[name] in factories.SINGLE_RELATIONS]
    ).prefetch_related(*[name for name in names if kinds[name] == 'm2m'])
    read = list(build.perms['list'])
    attrs = {
        '__module__': factories.__name__,
        'authentication_classes': (SessionAuthentication,),
        'permission_classes': (AllPermissionByAction,),
        'renderer_classes': (JSONRenderer,),
        'pagination_class': type('GridPagination', (GridPagination,),
                                 {'default_limit': build.page_size}),
        'filter_backends': (DjangoFilterBackend, SearchFilter, OrderingFilter),
        'serializer_class': row_serializer_for(build),
        'gtgrid_table_serializer': factories.cached(build, 'grid-table',
                                                    _table_serializer),
        'queryset': queryset,
        'search_fields': list(build.search_fields),
        'filterset_class': factories.filterset_for(build),
        'ordering_fields': [name for name in build.list_fields
                            if kinds[name] != 'm2m'] + ['pk', 'id'],
        'ordering': list(build.ordering),
        # Reading needs the list permissions; each row of a save is checked
        # against the permissions of what it does.
        'perms': {'list': read, 'retrieve': read, 'save': read,
                  'detail_template': read},
        'gtdesign_build': build,
        'optimistic_lock_required': build.optimistic_lock_required,
    }
    # ManagementMixin's get_object() (the conditions of the row) runs inside
    # OptimisticLockMixin's, which answers the ETag of the row read again.
    return type(factories.class_name(build, 'Grid'),
                (GridMixin, factories.ManagementMixin, OptimisticLockMixin,
                 viewsets.GenericViewSet), attrs)


def grid_viewset_for(build):
    """The viewset of an :class:`InteractiveGridBuild`: ``''`` lists,
    ``<pk>/`` reads one row and ``save/`` saves a batch."""
    return factories.cached(build, 'grid', _grid_viewset)


GRID_COMPONENTS = [InteractiveGridComponent]
