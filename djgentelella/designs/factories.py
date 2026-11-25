"""Serializers, filters and viewsets made at runtime from the builds.

What djgentelella-editor writes as code (``serializers.py``, ``api.py``,
``charts.py``) is made here as classes, while serving, from the same data:

* :func:`serializer_for` -- the ``list``, ``read`` and ``write`` serializers of
  an object management table;
* :func:`filterset_for` -- its django-filter ``FilterSet``;
* :func:`management_viewset_for` -- its ``AuthAllPermBaseObjectManagement``
  (or the inline variant), permissions per action from the build;
* :func:`chart_getter_for` -- a djgentelella.chartjs getter;
* :func:`stat_view_for` -- the viewset of a stat tile;
* :func:`crud_viewset_for` and :func:`facets_viewset_for` -- the classic CRUD
  pages and the facets of a table.

Every class is cached by ``(page hash, node id)`` (plus what it is), and kept
only while the build it was made from is equal to the one asked for: a page
published again, or a model exposed with other fields, gets new classes.

Every viewset authenticates with the session and checks
``AllPermissionByAction``; in a preview build (``build.preview``) every
queryset is empty.
"""

import json
import re
import threading
from collections import OrderedDict
from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.db.models import Q
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.utils.html import escape
from django.utils.text import capfirst
from django.utils.translation import gettext as _
from django_filters import (
    DateFromToRangeFilter, DateTimeFromToRangeFilter, FilterSet,
    ModelMultipleChoiceFilter,
)
from django_filters.widgets import CSVWidget
from rest_framework import serializers, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from djgentelella import chartjs
from djgentelella.cruds.base import CRUDMixin, CRUDView
from djgentelella.datasources import query
from djgentelella.datasources.base import ModelDataSource, api_error, get_datasource
from djgentelella.designs import notifications, pipeline
from djgentelella.designs.builds import TABLE_ACTIONS
from djgentelella.designs.conditions import (
    condition_object, denied, hidden_columns, row_conditions, row_denied,
    without_hidden,
)
from djgentelella.designs.introspection import NUMBER_KINDS, TEXT_KINDS
from djgentelella.fields.drfdatetime import DateRangeTextWidget, DateTimeRangeTextWidget
from djgentelella.fields.files import ChunkedFileField, GTBase64FileField
from djgentelella.forms import widgetmap
from djgentelella.locking import OptimisticLockMixin
from djgentelella.objectmanagement import (
    AuthAllPermBaseObjectManagement, BaseInlineObjectManagement,
)
from djgentelella.permission_management import (
    AllPermissionByAction, all_permission, get_actions_by_perms,
)
from djgentelella.serializers import GTDateField, GTDateTimeField
from djgentelella.serializers.selects import GTS2SerializerBase

__all__ = ['CHART_CLASSES', 'DesignDataSource', 'chart_getter_for', 'chart_rows',
           'clear_cache', 'crud_viewset_for', 'facets_viewset_for', 'filterset_for',
           'management_viewset_for', 'serializer_for', 'stat_value', 'stat_view_for']

#: Chart kind -> the djgentelella.chartjs getter it extends.
CHART_CLASSES = {
    'bar': chartjs.VerticalBarChart,
    'horizontal_bar': chartjs.HorizontalBarChart,
    'line': chartjs.LineChart,
    'pie': chartjs.PieChart,
    'doughnut': chartjs.DoughnutChart,
}
COLORS = [
    'rgba(38, 185, 154, 0.8)', 'rgba(52, 152, 219, 0.8)', 'rgba(155, 89, 182, 0.8)',
    'rgba(231, 76, 60, 0.8)', 'rgba(243, 156, 18, 0.8)', 'rgba(52, 73, 94, 0.8)',
    'rgba(26, 188, 156, 0.8)', 'rgba(149, 165, 166, 0.8)', 'rgba(211, 84, 0, 0.8)',
    'rgba(41, 128, 185, 0.8)',
]
SINGLE_RELATIONS = ('fk', 'o2o')
#: How many classes the cache keeps; a page has a handful per data node.
CACHE_SIZE = 512

_cache = OrderedDict()
_lock = threading.Lock()


def clear_cache():
    with _lock:
        _cache.clear()


def cached(build, kind, make):
    """``make(build)``, kept by ``(page hash, node id, kind)`` while the
    build stays equal to the one it was made from."""
    key = (build.page_hash, build.id, kind, build.preview)
    with _lock:
        hit = _cache.get(key)
        if hit is not None and hit[0] == build:
            _cache.move_to_end(key)
            return hit[1]
    value = make(build)
    with _lock:
        _cache[key] = (build, value)
        _cache.move_to_end(key)
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return value


def class_name(build, suffix):
    """``products`` + ``Serializer`` -> ``ProductsSerializer``."""
    return ''.join(part[:1].upper() + part[1:] for part in build.id.split('_')) + suffix


def field_kind(model, name):
    return widgetmap.field_kind(model._meta.get_field(name))


def json_value(value):
    """A number or a date as JSON can take it."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


# -- data sources over a design's model ----------------------------------------------

def search_q(fields, text):
    """DRF's ``SearchFilter`` as a ``Q``: every word in some of ``fields``."""
    query_q = Q()
    for word in re.split(r'[\s,]+', (text or '').strip()):
        if not word:
            continue
        word_q = Q()
        for name in fields:
            word_q |= Q(**{name + '__icontains': word})
        query_q &= word_q
    return query_q


class DesignDataSource(ModelDataSource):
    """The rows of a design's table as a data source.

    Its columns are the fields the model's exposure allows; ``search`` is
    applied the way the table's ``SearchFilter`` does it, on the table's
    ``search_fields``, so the facets count what the table shows. The
    permissions are not checked here but by the viewset that uses it.
    """

    def __init__(self, model, fields, *, queryset=None, search_fields=(), search=''):
        super().__init__(model, fields=list(fields), perms=[], queryset=queryset)
        self.search_fields = list(search_fields)
        self.search = search

    def base_queryset(self, request):
        queryset = super().base_queryset(request)
        if self.search and self.search_fields:
            queryset = queryset.filter(search_q(self.search_fields, self.search))
        return queryset


def allowed_columns(model, exposed_fields):
    """The column names of ``model`` a design's data source offers."""
    return [model_field.name for model_field in exposed_fields
            if widgetmap.field_kind(model_field) not in ('file', 'image', 'binary')]


def valid_pk(model, value):
    """Whether ``value`` can be a primary key of ``model``."""
    try:
        model._meta.pk.to_python(value)
    except DjangoValidationError:
        return False
    return True


def parent_or_none(model, pk):
    if pk is None or not valid_pk(model, pk):
        return None
    return model._default_manager.filter(pk=pk).first()


def check_perms(request, perms):
    if not all_permission(request.user, list(perms)):
        raise PermissionDenied()


# -- serializers ------------------------------------------------------------------

def _date_field(model_field, kind, **kwargs):
    field_class = GTDateTimeField if kind == 'datetime' else GTDateField
    # An empty date is None, which a NOT NULL column refuses: then it is an
    # invalid date (400), not an IntegrityError.
    return field_class(allow_empty_str=model_field.null, **kwargs)


def _required(model_field):
    return not (model_field.blank or model_field.has_default())


def _list_field(model_field):
    kind = widgetmap.field_kind(model_field)
    if kind in ('date', 'datetime'):
        return _date_field(model_field, kind, read_only=True)
    if kind in SINGLE_RELATIONS:
        return GTS2SerializerBase(read_only=True)
    if kind == 'm2m':
        return GTS2SerializerBase(many=True, read_only=True)
    return None


def _write_field(model_field, upload):
    kind = widgetmap.field_kind(model_field)
    if upload:
        return ChunkedFileField(required=_required(model_field))
    if kind in ('date', 'datetime'):
        return _date_field(model_field, kind, required=_required(model_field))
    if kind in ('file', 'image'):
        return GTBase64FileField(required=_required(model_field),
                                 allow_empty_file=False)
    return None


def _read_field(model_field, upload):
    return _list_field(model_field) or _write_field(model_field, upload)


#: Row icon -> the action (``action_conditions``) it runs.
ROW_ICONS = {'destroy': 'destroy', 'update': 'update', 'detail': 'retrieve'}


def _actions_method(build):
    action_perms = {'destroy': build.perms['destroy'], 'update': build.perms['update'],
                    'detail': build.perms['retrieve']}
    per_row = bool(row_conditions(build))

    def get_actions(self, obj):
        # Which row icons (detail, update, delete) the user gets: the
        # permissions, the conditions of the actions (gtdesign_denied) and
        # those evaluated with this row.
        request = self.context['request']
        actions = get_actions_by_perms(request.user, action_perms)
        refused = set(self.context.get('gtdesign_denied') or ())
        if per_row:
            refused |= row_denied(build, request, obj)
        return {icon: allowed and ROW_ICONS[icon] not in refused
                for icon, allowed in actions.items()}
    return get_actions


def _display_method(name, many):
    if many:
        def get_display(self, obj):
            return ', '.join(str(related) for related in getattr(obj, name).all())
    else:
        def get_display(self, obj):
            related = getattr(obj, name)
            return str(related) if related is not None else ''
    return get_display


def display_fields(build):
    """The list fields the detail shows as text: relations and choices."""
    return [name for name in build.list_fields
            if field_kind(build.model, name) in SINGLE_RELATIONS + ('m2m', 'choices')]


def read_fields(build):
    return build.form.field_names + [name for name in build.list_fields
                                     if name not in build.form.field_names]


def _make_serializer(build, role):
    model = build.model
    opts = model._meta
    attrs = {'__module__': __name__}
    uploads = {form_field.name for form_field in build.form.fields
               if form_field.widget in widgetmap.UPLOAD_WIDGETS}
    alias = opts.pk.name != 'id'
    if role == 'list':
        names = build.list_fields
        for name in names:
            declared = _list_field(opts.get_field(name))
            if declared is not None:
                attrs[name] = declared
        attrs['actions'] = serializers.SerializerMethodField()
        attrs['get_actions'] = _actions_method(build)
        meta_fields = ['id'] + names + ['actions']
    elif role == 'write':
        names = build.form.field_names
        for name in names:
            declared = _write_field(opts.get_field(name), name in uploads)
            if declared is not None:
                attrs[name] = declared
        meta_fields = list(names)
        alias = False
    elif role == 'read':
        names = read_fields(build)
        for name in names:
            declared = _read_field(opts.get_field(name), name in uploads)
            if declared is not None:
                attrs[name] = declared
        meta_fields = ['id'] + names
        for name in display_fields(build):
            kind = field_kind(model, name)
            if kind == 'choices':
                attrs[name + '_display'] = serializers.CharField(
                    source='get_%s_display' % name, read_only=True)
            else:
                attrs[name + '_display'] = serializers.SerializerMethodField()
                attrs['get_%s_display' % name] = _display_method(name, kind == 'm2m')
            meta_fields.append(name + '_display')
    else:
        raise ValueError('role must be list, read or write, not %r' % (role,))
    if alias:
        # ObjectCRUD reads data.id, whatever the primary key is called.
        attrs['id'] = serializers.ReadOnlyField(source='pk')
    attrs['Meta'] = type('Meta', (), {'model': model, 'fields': meta_fields})
    return type(class_name(build, role.capitalize() + 'Serializer'),
                (serializers.ModelSerializer,), attrs)


def serializer_for(build, role):
    """The ``list``, ``read`` or ``write`` serializer of an
    :class:`~djgentelella.designs.builds.ObjectManagementBuild`.

    ``list`` is a table row (relations as ``{id, text}``, plus the row's
    ``actions``); ``write`` creates and updates (the form's fields, relations
    as primary keys); ``read`` fills the update form and the detail, with a
    ``<name>_display`` text for the relations and choices of the list.
    """
    return cached(build, 'serializer-' + role,
                  lambda item: _make_serializer(item, role))


def table_serializer_for(build):
    def make(item):
        row = serializer_for(item, 'list')
        return type(class_name(item, 'TableSerializer'), (serializers.Serializer,), {
            '__module__': __name__,
            'data': serializers.ListField(child=row(), required=True),
            'draw': serializers.IntegerField(required=True),
            'recordsFiltered': serializers.IntegerField(required=True),
            'recordsTotal': serializers.IntegerField(required=True),
        })
    return cached(build, 'table-serializer', make)


# -- filters ------------------------------------------------------------------------

def _make_filterset(build):
    model = build.model
    meta_fields = {}
    attrs = {'__module__': __name__}
    for name in build.list_fields:
        model_field = model._meta.get_field(name)
        kind = widgetmap.field_kind(model_field)
        if kind in TEXT_KINDS:
            meta_fields[name] = ['icontains']
        elif kind in NUMBER_KINDS + SINGLE_RELATIONS + ('boolean', 'nullboolean',
                                                        'choices'):
            meta_fields[name] = ['exact']
        elif kind == 'date':
            attrs[name] = DateFromToRangeFilter(
                widget=DateRangeTextWidget(attrs={'placeholder': 'YYYY/MM/DD'}))
        elif kind == 'datetime':
            attrs[name] = DateTimeFromToRangeFilter(
                widget=DateTimeRangeTextWidget(
                    attrs={'placeholder': 'YYYY/MM/DD HH:MM:SS'}))
        elif kind == 'm2m':
            attrs[name] = ModelMultipleChoiceFilter(
                queryset=model_field.related_model._default_manager.all(),
                widget=CSVWidget())
    attrs['Meta'] = type('Meta', (), {'model': model, 'fields': meta_fields})
    return type(class_name(build, 'FilterSet'), (FilterSet,), attrs)


def filterset_for(build):
    """The ``FilterSet`` of a table: one filter per list column that can have
    one -- ``icontains`` on text, ``exact`` on numbers, relations, booleans and
    choices, a range on dates, a CSV of pks on many-to-many."""
    return cached(build, 'filterset', _make_filterset)


# -- object management ---------------------------------------------------------------

def parse_filters(raw):
    """The ``gtfilters`` query parameter: a JSON list of filters of the
    parameter document (:mod:`djgentelella.datasources.query`)."""
    try:
        filters = json.loads(raw)
    except ValueError:
        raise ValidationError({'gtfilters': [_('not valid JSON')]})
    if not isinstance(filters, list) or not all(isinstance(item, dict)
                                                for item in filters):
        raise ValidationError({'gtfilters': [_('must be a list of filter objects')]})
    return filters


def apply_filters(source, request, queryset, filters):
    """The ``filters`` of a parameter document on ``queryset``; an invalid
    one is a 400."""
    try:
        return query.apply_filters(source, request, queryset, filters,
                                   source.column_map(request))
    except DjangoValidationError as error:
        raise api_error(error, 'gtfilters')


def parent_link(request):
    """The URL of the design page the request comes from, for notices."""
    page = getattr(request, 'gtdesign_page', None)
    if page is None:
        return None
    path = page.path
    parent_pk = getattr(request, 'gtdesign_parent_pk', None)
    if parent_pk is not None:
        path = '%s/%s' % (path, parent_pk)
    return reverse('gt-design-page', args=[path])


class TablePagination(LimitOffsetPagination):
    """Pages of 10 rows unless the table asks; never more than 1000."""

    default_limit = 10
    max_limit = 1000


def without_columns(filterset_class, hidden):
    """``filterset_class`` without the filters of the ``hidden`` columns."""
    subclass = type(filterset_class.__name__, (filterset_class,),
                    {'__module__': __name__})
    subclass.base_filters = {
        name: item for name, item in filterset_class.base_filters.items()
        if (item.field_name or name).split('__')[0] not in hidden}
    return subclass


class ManagementMixin:
    """What a design's management viewset adds to djgentelella's.

    The conditions of the build (:mod:`djgentelella.designs.conditions`):
    an action refused by its condition is a 403 -- one evaluated per row,
    when the row is read (:meth:`get_object`) --, and a hidden column leaves
    the rows, the detail, the values of the update form, the search, the
    filters and the ordering -- the one the request asks and the default
    one. An update leaves it as it is: it is not read from the request.
    Creating a row still takes it (writing a new row reveals nothing; the
    ``create`` action has its own condition).
    """

    gtdesign_build = None
    gtdesign_hidden = frozenset()
    gtdesign_denied = frozenset()

    def gtdesign_condition_object(self):
        """The object the conditions hold: an inline table's parent."""
        if self.gtdesign_build.inline:
            return self.get_parent_object()
        return None

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        build = self.gtdesign_build
        if not (build.column_conditions or build.action_conditions):
            return
        obj = self.gtdesign_condition_object()
        self.gtdesign_denied = frozenset(denied(build, request, obj))
        for name, actions in TABLE_ACTIONS.items():
            if self.action in actions and name in self.gtdesign_denied:
                raise PermissionDenied()
        hidden = frozenset(hidden_columns(build, request, obj))
        self.gtdesign_hidden = hidden
        if hidden:
            self.search_fields = [name for name in self.search_fields
                                  if name not in hidden]
            self.ordering_fields = [name for name in self.ordering_fields
                                    if name not in hidden]
            # The default order would tell the hidden values apart too.
            self.ordering = without_hidden(
                self.ordering or build.model._meta.ordering, hidden) or ['-pk']
            self.filterset_class = without_columns(self.filterset_class, hidden)

    def get_object(self):
        obj = super().get_object()
        build = self.gtdesign_build
        if row_conditions(build):
            refused = row_denied(build, self.request, obj)
            for name, actions in TABLE_ACTIONS.items():
                if self.action in actions and name in refused:
                    raise PermissionDenied()
        return obj

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['gtdesign_denied'] = self.gtdesign_denied
        return context

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        hidden = self.gtdesign_hidden
        if not hidden:
            return serializer
        if self.action == 'list':
            fields = serializer.fields['data'].child.fields
        elif self.action in ('retrieve', 'get_values_for_update', 'update',
                             'partial_update'):
            # An update neither shows nor writes it: the row keeps its value.
            fields = serializer.fields
        else:
            return serializer
        for name in hidden:
            fields.pop(name, None)
            fields.pop(name + '_display', None)
        return serializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.gtdesign_build.preview:
            return queryset.none()
        return queryset

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        raw = self.request.query_params.get('gtfilters')
        if raw:
            build = self.gtdesign_build
            source = DesignDataSource(build.model, [
                name for name in build.columns if name not in self.gtdesign_hidden])
            queryset = apply_filters(source, self.request, queryset,
                                     parse_filters(raw))
        return queryset

    def get_parent_queryset(self):
        # DRF permissions are per model, not per object: who may reach the
        # rows of a parent needs the view permissions of the parent model too.
        check_perms(self.request, self.gtdesign_build.parent_perms)
        return super().get_parent_queryset()

    def get_parent_object(self):
        try:
            parent = super().get_parent_object()
        except (ValueError, TypeError, DjangoValidationError):
            # A pk the parent's primary key cannot read ('x' for an integer).
            raise Http404(_('No such parent'))
        self.request.gtdesign_parent_pk = parent.pk
        return parent

    def _notify(self, event, instance):
        build = self.gtdesign_build
        if build.notify is not None and build.notify.actions_for(event):
            notifications.notify(build.notify, event, instance, self.request.user,
                                 link=parent_link(self.request))

    #: Where the ``on_submit`` pipeline's branch goes after a save: the
    #: response carries it as ``gtdesign_redirect``.
    gtdesign_redirect = None

    def gtdesign_run_pipeline(self, serializer, save):
        """``save()`` through the ``on_submit`` pipeline of the build
        (:mod:`djgentelella.designs.pipeline`): its validations and
        computations first, then the save and its processes in one
        transaction. Its errors are a 400; its branch, the
        ``gtdesign_redirect`` of the response. Runs after the permissions,
        the conditions and the version (C9) were checked."""
        build = self.gtdesign_build
        if not build.pipeline:
            save()
            return
        hidden = () if self.action == 'create' else self.gtdesign_hidden
        ctx = pipeline.PipelineContext(
            self.request, node=build.id, form=serializer,
            data=serializer.validated_data, instance=serializer.instance,
            model=build.model,
            fields=[name for name in build.form.field_names if name not in hidden])

        def do_save(ctx):
            save()
            return serializer.instance

        result = pipeline.run_pipeline(build.pipeline, ctx, save=do_save)
        if not result.ok:
            raise ValidationError(pipeline.serializer_errors(result))
        self.gtdesign_redirect = result.url

    def perform_create(self, serializer):
        self.gtdesign_run_pipeline(
            serializer, lambda: super(ManagementMixin, self).perform_create(serializer))
        self._notify('create', serializer.instance)

    def perform_update(self, serializer):
        self.gtdesign_run_pipeline(
            serializer, lambda: super(ManagementMixin, self).perform_update(serializer))
        self._notify('update', serializer.instance)

    def finalize_response(self, request, response, *args, **kwargs):
        if self.gtdesign_redirect and isinstance(getattr(response, 'data', None),
                                                 dict):
            response.data['gtdesign_redirect'] = self.gtdesign_redirect
        return super().finalize_response(request, response, *args, **kwargs)

    def perform_destroy(self, instance):
        # Before deleting: the notification still reads the row.
        self._notify('delete', instance)
        super().perform_destroy(instance)

    @action(detail=False, methods=['get'])
    def detail_template(self, request, *args, **kwargs):
        """The squirrelly template of the detail modal (escaped by squirrelly)."""
        build = self.gtdesign_build
        shown = set(display_fields(build))
        rows = []
        for name in build.list_fields:
            if name in self.gtdesign_hidden:
                continue
            model_field = build.model._meta.get_field(name)
            if widgetmap.field_kind(model_field) in ('file', 'image'):
                continue
            rows.append('<dt>%s</dt><dd><%% it.%s %%></dd>' % (
                escape(capfirst(str(model_field.verbose_name))),
                name + ('_display' if name in shown else '')))
        title = '<%% it.%s %%>' % delete_display(build)
        return Response({'title': title, 'template': '<dl>%s</dl>' % ''.join(rows)})


def delete_display(build):
    """The column a row is named by in the delete and detail modals."""
    for name in build.list_fields:
        if field_kind(build.model, name) in TEXT_KINDS:
            return name
    return 'id'


def _management_viewset(build):
    model = build.model
    names = read_fields(build)
    kinds = {name: field_kind(model, name) for name in names}
    queryset = model._default_manager.select_related(
        *[name for name in names if kinds[name] in SINGLE_RELATIONS]
    ).prefetch_related(*[name for name in names if kinds[name] == 'm2m'])
    write = serializer_for(build, 'write')
    read = serializer_for(build, 'read')
    attrs = {
        '__module__': __name__,
        'authentication_classes': (SessionAuthentication,),
        'permission_classes': (AllPermissionByAction,),
        'renderer_classes': (JSONRenderer,),
        'pagination_class': TablePagination,
        'serializer_class': {
            'list': table_serializer_for(build),
            'create': write,
            'update': write,
            'partial_update': write,
            'retrieve': read,
            'get_values_for_update': read,
        },
        'queryset': queryset,
        'search_fields': list(build.search_fields),
        'filterset_class': filterset_for(build),
        'ordering_fields': [name for name in build.list_fields
                            if kinds[name] != 'm2m'] + ['pk', 'id'],
        'ordering': list(build.ordering),
        'perms': {key: list(value) for key, value in build.perms.items()},
        'gtdesign_build': build,
    }
    bases = (ManagementMixin, AuthAllPermBaseObjectManagement)
    if build.inline:
        bases = (ManagementMixin, BaseInlineObjectManagement,
                 AuthAllPermBaseObjectManagement)
        attrs.update(parent_model=build.parent_model, parent_field=build.parent_field)
    if build.optimistic_lock:
        # Its get_object() goes through ManagementMixin's: the conditions
        # (403) come before the version (409).
        bases = (bases[0], OptimisticLockMixin) + bases[1:]
        attrs['optimistic_lock_required'] = build.optimistic_lock_required
    return type(class_name(build, 'Management'), bases, attrs)


def management_viewset_for(build):
    """The ``AuthAllPermBaseObjectManagement`` of a table, or the inline
    variant (``BaseInlineObjectManagement``) when it has a parent."""
    return cached(build, 'management', _management_viewset)


# -- charts and stats ----------------------------------------------------------------

def source_for(build, request):
    """The data source a chart or stat reads: its data source, checked, or
    a :class:`DesignDataSource` over its model."""
    if build.datasource:
        try:
            source = get_datasource(build.datasource)
        except KeyError:
            raise PermissionDenied()
        if not source.has_permission(request):
            raise PermissionDenied()
        return source
    return DesignDataSource(build.model, build.columns)


def _aggregate_spec(build):
    if build.aggregate == 'count' and not build.value_field:
        return {'fn': 'count'}, 'count'
    column = build.value_field or 'pk'
    return ({'column': column, 'fn': build.aggregate},
            '%s__%s' % (column, build.aggregate))


SAMPLE_LABELS = ['A', 'B', 'C', 'D', 'E']


def chart_facet_filters(build, request):
    """The filters of the facets the chart follows (``gtfilters``, as the
    table of its panel receives them): only on the panel's columns, and not
    on one its table hides for ``request`` (``column_conditions``). Any
    other filter is a 400; without ``facets`` the chart takes none."""
    raw = request.GET.get('gtfilters')
    if not raw:
        return []
    if not build.facets:
        raise ValidationError({'gtfilters': [_('this chart follows no facets')]})
    filters = parse_filters(raw)
    allowed = set(build.facet_columns)
    resolved = getattr(request, 'gtdesign_resolved', None)
    target = resolved.nodes.get(build.facets_target) if resolved is not None \
        else None
    if target is not None and getattr(target.build, 'column_conditions', None):
        allowed -= set(hidden_columns(target.build, request))
    for item in filters:
        if item.get('column') not in allowed:
            raise ValidationError({'gtfilters': [
                _('%r is not a facet of this chart') % (item.get('column'),)]})
    return filters


def chart_rows(build, request):
    """``[{'label', 'value'}]``: one per group, at most ``build.limit``.

    Groups by a date are in date order and leave the rows without a date out;
    the others go from the largest value down.
    """
    if build.preview:
        return [{'label': label, 'value': 5 - index}
                for index, label in enumerate(SAMPLE_LABELS[:build.limit])]
    source = source_for(build, request)
    spec, key = _aggregate_spec(build)
    group = {'column': build.group_by, 'period': build.period} if build.period \
        else build.group_by
    params = {'group_by': [group], 'aggregates': [spec],
              'filters': chart_facet_filters(build, request)}
    if build.period:
        params['filters'].append({'column': build.group_by, 'op': 'isnull',
                                  'value': False})
    try:
        # In the database: the largest values first (or the dates in order)
        # and only as many groups as the chart draws.
        rows = query.aggregate(source, request, params,
                               order_by_value=not build.period, limit=build.limit)
    except DjangoValidationError as error:
        raise api_error(error)
    result = []
    for row in rows:
        value = row[build.group_by]
        if build.period:
            label = query.period_label(build.period, value)
        elif build.group_by + '__display' in row:
            label = row[build.group_by + '__display']
        else:
            label = value
        result.append({'label': '-' if label is None else str(label),
                       'value': json_value(row[key]) or 0})
    return result


def _make_chart_getter(build):
    base = CHART_CLASSES[build.chart]
    number = int if build.circular else float

    def get_rows(self):
        if not hasattr(self, '_rows'):
            self._rows = chart_rows(build, self.request)
        return self._rows

    def get_labels(self):
        return [row['label'] for row in self.get_rows()]

    def get_datasets(self):
        rows = self.get_rows()
        dataset = {'label': build.title,
                   'data': [number(row['value'] or 0) for row in rows]}
        if build.circular:
            dataset['backgroundColor'] = [COLORS[index % len(COLORS)]
                                          for index in range(len(rows))]
        else:
            dataset['backgroundColor'] = dataset['borderColor'] = COLORS[0]
        return [dataset]

    attrs = {
        '__module__': __name__,
        'authentication_classes': (SessionAuthentication,),
        'permission_classes': (AllPermissionByAction,),
        'renderer_classes': (JSONRenderer,),
        'perms': {'list': list(build.perms)},
        'gtdesign_build': build,
        'get_rows': get_rows,
        'get_labels': get_labels,
        'get_datasets': get_datasets,
    }
    if build.circular:
        # The page gives the chart a fixed height; it fits in it, not square.
        attrs['get_maintainAspectRatio'] = lambda self: False
    return type(class_name(build, 'Chart'), (base,), attrs)


def chart_getter_for(build):
    """A djgentelella.chartjs getter (``VerticalBarChart``, ``PieChart``...)
    of a :class:`~djgentelella.designs.builds.ChartBuild`."""
    return cached(build, 'chart', _make_chart_getter)


def _aggregate_value(source, request, spec, key, filters=()):
    rows = query.aggregate(source, request, {'aggregates': [spec],
                                             'filters': list(filters)})
    return json_value(rows[0][key]) if rows else None


def stat_value(build, request):
    """``{'value', 'previous', 'change'}`` of a stat.

    Without a comparison ``previous`` and ``change`` are ``None``. With one,
    ``value`` is the current period's (``build.period`` of
    ``build.compare_field``), ``previous`` the one before, and ``change`` the
    difference in percent (``None`` when the previous one is zero or empty).
    """
    if build.preview:
        return {'value': 42, 'previous': 40 if build.compare_field else None,
                'change': 5.0 if build.compare_field else None}
    source = source_for(build, request)
    spec, key = _aggregate_spec(build)
    try:
        if not build.compare_field:
            return {'value': _aggregate_value(source, request, spec, key),
                    'previous': None, 'change': None}
        periods = [[{'column': build.compare_field, 'op': 'date_period',
                     'value': {'period': build.period, 'offset': offset}}]
                   for offset in (0, -1)]
        value, previous = (_aggregate_value(source, request, spec, key, filters)
                           for filters in periods)
    except DjangoValidationError as error:
        raise api_error(error)
    change = None
    if previous:
        change = round(((value or 0) - previous) * 100.0 / abs(previous), 1)
    return {'value': value, 'previous': previous, 'change': change}


def _make_stat_view(build):
    def list_view(self, request, *args, **kwargs):
        return Response(stat_value(build, request))

    return type(class_name(build, 'StatViewSet'), (viewsets.ViewSet,), {
        '__module__': __name__,
        'authentication_classes': (SessionAuthentication,),
        'permission_classes': (AllPermissionByAction,),
        'renderer_classes': (JSONRenderer,),
        'perms': {'list': list(build.perms)},
        'gtdesign_build': build,
        'list': list_view,
    })


def stat_view_for(build):
    """The viewset of a stat tile: ``GET`` answers :func:`stat_value`."""
    return cached(build, 'stat', _make_stat_view)


# -- facets ------------------------------------------------------------------------

def _make_facets_viewset(build):
    def target_build(request):
        return request.gtdesign_resolved.nodes[build.target].build

    def source(self, request, search=''):
        """The data source of the target's rows, and the facet columns the
        request may see: not those its table hides (column_conditions)."""
        target = target_build(request)
        queryset = target.model._default_manager.all()
        parent = None
        if build.inline:
            check_perms(request, target.parent_perms)
            parent = parent_or_none(target.parent_model, self.kwargs.get('parent_pk'))
            if parent is None:
                raise Http404(_('No such parent'))
            queryset = queryset.filter(**{target.parent_field: parent})
        if build.preview:
            queryset = queryset.none()
        hidden = hidden_columns(target, request, parent) \
            if getattr(target, 'column_conditions', None) else set()
        search_fields = [name for name in target.search_fields if name not in hidden]
        return DesignDataSource(
            build.model, [name for name in build.columns if name not in hidden],
            queryset=queryset, search_fields=search_fields, search=search)

    def list_view(self, request, *args, **kwargs):
        # What GTFacets reads first: the columns, their labels and kinds.
        data_source = source(self, request)
        columns = data_source.column_map(request)
        return Response({'name': build.id, 'label': build.title,
                         'columns': [columns[name].as_dict()
                                     for name in build.columns if name in columns],
                         'formats': []})

    def facets_view(self, request, *args, **kwargs):
        try:
            params = query.parse_params(request.query_params.get('params'))
            wanted = request.query_params.get('columns')
            # The search narrows the rows of the source, not its columns: one
            # source answers both.
            search, params['search'] = params['search'], ''
            data_source = source(self, request, search)
            shown = data_source.fields
            names = [name for name in (wanted or '').split(',') if name] \
                or [name for name in build.columns if name in shown]
            if any(name not in build.columns or name not in shown
                   for name in names):
                raise DjangoValidationError(_('unknown facet column'))
            if build.preview:
                return Response({name: [] for name in names})
            return Response(query.facets(data_source, request, params, names))
        except DjangoValidationError as error:
            raise api_error(error)

    facets_view.__name__ = 'facets'
    return type(class_name(build, 'FacetsViewSet'), (viewsets.ViewSet,), {
        '__module__': __name__,
        'authentication_classes': (SessionAuthentication,),
        'permission_classes': (AllPermissionByAction,),
        'renderer_classes': (JSONRenderer,),
        'perms': {'list': list(build.perms), 'facets': list(build.perms)},
        'gtdesign_build': build,
        'list': list_view,
        'facets': action(detail=False, methods=['get'])(facets_view),
    })


def facets_viewset_for(build):
    """The endpoint GTFacets (djgentelella.datasources) reads: ``''`` is the
    description of the columns and ``facets`` the counts, over
    the rows of the target table."""
    return cached(build, 'facets', _make_facets_viewset)


# -- the classic CRUD ------------------------------------------------------------------

class DesignCRUDMixin(CRUDMixin):
    """CRUDMixin with the URLs of the design router instead of named ones.

    The conditions of the build (:mod:`djgentelella.designs.conditions`) are
    the view's ``column_conditions`` and ``action_conditions``
    (:class:`~djgentelella.cruds.base.CRUDMixin`): they hide columns from the
    list, the detail, the search and the update form, and a page refused by
    its condition loses its links (the viewset answers 403).
    """

    gtdesign_build = None

    def gtdesign_base(self):
        return self.request.gtdesign_crud_base

    def get_condition_object(self):
        """The object of the page about one object, when the build's
        endpoints carry it (:func:`~djgentelella.designs.conditions.
        condition_object`)."""
        return condition_object(self.gtdesign_build, self.request)

    def gtdesign_conditions(self):
        """``(hidden columns, refused pages)`` for the request."""
        return self.get_hidden_columns(), self.get_denied_actions()

    def get_urls_and_fields(self, context):
        super().get_urls_and_fields(context)
        base = self.gtdesign_base()
        views = self.views_available
        context['url_list'] = base if 'list' in views else None
        context['url_create'] = base + 'create/' if 'create' in views else None
        context['crud_base'] = base
        obj = getattr(self, 'object', None)
        if isinstance(obj, models.Model) and obj.pk is not None:
            for name, suffix in (('detail', ''), ('update', 'update/'),
                                 ('delete', 'delete/')):
                context['url_' + name] = ('%s%s/%s' % (base, obj.pk, suffix)
                                          if name in views else None)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        names = self.list_fields if self.view_type == 'list' else \
            getattr(self, 'display_fields', None) or []
        hidden = self.get_hidden_columns()
        context['gtdesign_columns'] = [
            (name, capfirst(str(self.model._meta.get_field(name).verbose_name)))
            for name in names if name not in hidden]
        if getattr(self.request, 'gtdesign_embed', False):
            context['template_father'] = 'gtdesigns/crud/fragment.html'
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.gtdesign_preview:
            return queryset.none()
        if not queryset.ordered:
            # Without Meta.ordering, or when CRUDMixin dropped every ordering
            # over a hidden column, a paginated list still needs an order:
            # -pk in both cases, so a condition that shows or hides a column
            # does not reorder the rows.
            queryset = queryset.order_by('-pk')
        return queryset

    def get_success_url(self):
        return self.gtdesign_base()

    def form_valid(self, form):
        """The save of the create and update pages, through the ``on_submit``
        pipeline of the build (:mod:`djgentelella.designs.pipeline`): its
        errors show on the form, nothing saved; its branch is where the page
        goes after saving."""
        build = self.gtdesign_build
        if not build.pipeline:
            return super().form_valid(form)
        hidden = self.get_hidden_columns() if self.view_type == 'update' else ()
        ctx = pipeline.context_for_form(
            form, self.request, node=build.id,
            fields=[name for name in form.fields if name not in hidden])
        responses = []

        def save(ctx):
            responses.append(super(DesignCRUDMixin, self).form_valid(form))
            return self.object

        result = pipeline.run_pipeline(build.pipeline, ctx, save=save)
        if not result.ok:
            if self.view_type == 'create':
                self.object = None
            pipeline.form_errors_to(form, result)
            return self.form_invalid(form)
        if result.url:
            return HttpResponseRedirect(result.url)
        return responses[0]


class DesignCRUDView(CRUDView):
    """A ``CRUDView`` of a :class:`~djgentelella.designs.builds.CrudBuild`,
    served by the design router."""

    template_name_base = 'gtdesigns/crud'
    mixin = DesignCRUDMixin

    def __init__(self, build):
        self.build = build
        self.model = build.model
        self.list_fields = list(build.list_fields)
        self.display_fields = list(build.detail_fields)
        self.search_fields = [name + '__icontains' for name in build.search_fields]
        self.views_available = list(build.views)
        self.paginate_by = build.paginate_by
        if build.form is not None:
            self.add_form = self.update_form = build.form.form_class
        self.column_conditions = dict(build.column_conditions or {})
        self.action_conditions = dict(build.action_conditions or {})
        self.optimistic_lock = build.optimistic_lock
        self.optimistic_lock_required = build.optimistic_lock_required
        self.mixin = type('BoundDesignCRUDMixin', (DesignCRUDMixin,),
                          {'gtdesign_preview': build.preview,
                           'gtdesign_build': build})
        super().__init__(mixin=self.mixin)

    def initialize_perms(self):
        # From the build, with nothing written to the database (CRUDView
        # creates missing view permissions).
        self.perms = {view: list(perms) for view, perms in self.build.perms.items()}


def _make_crud_viewset(build):
    crud = DesignCRUDView(build)

    def delegate(view_name):
        def view(self, request, *args, **kwargs):
            cond = (build.action_conditions or {}).get(view_name)
            if cond is not None and view_name in denied(
                    build, request, condition_object(build, request)):
                raise PermissionDenied()
            if 'pk' in kwargs and not valid_pk(build.model, kwargs['pk']):
                raise Http404(_('No such object'))
            django_request = request._request
            django_request.gtdesign_crud_base = crud_base(request)
            return getattr(crud, view_name)(django_request, *args, **kwargs)
        view.__name__ = view_name if view_name in ('list',) else view_name + '_page'
        return view

    attrs = {
        '__module__': __name__,
        'authentication_classes': (SessionAuthentication,),
        'permission_classes': (AllPermissionByAction,),
        'renderer_classes': (JSONRenderer,),
        'perms': {'list': build.perms['list'], 'retrieve': build.perms['detail'],
                  'create_page': build.perms['create'],
                  'update_page': build.perms['update'],
                  'delete_page': build.perms['delete']},
        'gtdesign_build': build,
        'gtdesign_crud': crud,
    }
    if 'list' in build.views:
        attrs['list'] = delegate('list')
    if 'detail' in build.views:
        attrs['retrieve'] = delegate('detail')
        attrs['retrieve'].__name__ = 'retrieve'
    for view_name in ('create', 'update', 'delete'):
        if view_name in build.views:
            attrs[view_name + '_page'] = action(
                detail=view_name != 'create', methods=['get', 'post'],
                url_path=view_name)(delegate(view_name))
    return type(class_name(build, 'CrudViewSet'), (viewsets.ViewSet,), attrs)


def crud_base(request):
    """The URL the classic CRUD of the request's node is mounted at."""
    return reverse('gt-design-endpoint', kwargs={
        'page_id': request.gtdesign_page.pk, 'node_id': request.gtdesign_node.id,
        'rest': ''})


def crud_viewset_for(build):
    """The classic CRUD pages (``CRUDView``) of a
    :class:`~djgentelella.designs.builds.CrudBuild` as one viewset: ``''``
    lists, ``create/``, ``<pk>/``, ``<pk>/update/`` and ``<pk>/delete/``."""
    return cached(build, 'crud', _make_crud_viewset)


def crud_view_for(build):
    """The :class:`DesignCRUDView` the viewset of ``build`` delegates to."""
    return crud_viewset_for(build).gtdesign_crud
