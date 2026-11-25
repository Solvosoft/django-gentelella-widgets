"""The ``DataSource`` interface and its registry.

A data source answers three questions -- which columns, which rows, who may
look -- and nothing else. Filtering, grouping and exporting are done by
``query`` and ``export`` against any object that answers them, so a project
can write a source by hand (:class:`DataSource`), derive one from a model
(:class:`ModelDataSource`) or wrap a function (:class:`FunctionDataSource`).

Sources live in ``<app>/gtdatasources.py`` and are registered with
:func:`register_datasource`; the module is imported from the app's
``AppConfig.ready()``, like ``gtflows``.
"""

import inspect
import logging
import warnings
from dataclasses import dataclass, field as dc_field

from django.apps import apps
from django.core.exceptions import (
    FieldDoesNotExist, ObjectDoesNotExist, PermissionDenied,
)
from django.db import models
from django.db.models import Q
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException

from djgentelella.sites import get_current_site, site_q
from djgentelella.autodiscover import autodiscover_once

logger = logging.getLogger(__name__)

#: Every column kind the query engine understands.
KINDS = ('string', 'text', 'integer', 'decimal', 'boolean', 'date', 'datetime',
         'fk', 'm2m', 'choices', 'json')
NUMERIC_KINDS = ('integer', 'decimal')
TEXT_KINDS = ('string', 'text')
DATE_KINDS = ('date', 'datetime')


class DataSourceUnavailable(APIException):
    """The rows of a source cannot be read right now: the external API it
    reads is down, timed out or answered something it cannot use.

    It is not a bad request (that is a ``ValidationError``, a 400): the same
    parameters may work later. A DRF ``APIException``, so every endpoint of
    djgentelella -- the data source API, the components of a design -- answers
    it with its ``status_code`` and ``{"detail": ...}``:

    * 503 (the default): the source is unavailable;
    * 502 (``status=502``): the source upstream answered, but with an error
      or a body it cannot read;
    * 504 (``status=504``): the source upstream did not answer in time.

    ``retry_after`` (seconds) becomes the ``Retry-After`` header.
    """
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = _('The data source is not available right now.')
    default_code = 'datasource_unavailable'
    #: The status codes it may carry.
    STATUSES = (status.HTTP_502_BAD_GATEWAY, status.HTTP_503_SERVICE_UNAVAILABLE,
                status.HTTP_504_GATEWAY_TIMEOUT)

    def __init__(self, detail=None, code=None, *, status=None, retry_after=None):
        super().__init__(detail, code)
        if status is not None:
            if status not in self.STATUSES:
                raise ValueError('DataSourceUnavailable takes a status of %s, '
                                 'not %r' % (self.STATUSES, status))
            self.status_code = status
        #: DRF's exception handler sends it as ``Retry-After``.
        self.wait = retry_after


def takes_params(source):
    """Whether ``source.get_queryset`` takes the query parameters: its
    signature has a ``params`` argument (``get_queryset(request,
    params=None)``)."""
    method = getattr(source, 'get_queryset', None)
    if method is None:
        return False
    try:
        return 'params' in inspect.signature(method).parameters
    except (TypeError, ValueError):
        return False


def project_model_of(source):
    """The model of the project behind ``source`` -- its rows are rows of that
    model, its pks are that model's -- or None: :attr:`DataSource.
    project_model`, and for an object that is no :class:`DataSource` its
    ``model`` attribute (deprecated)."""
    if isinstance(source, DataSource):
        return source.project_model
    if hasattr(source, 'project_model'):
        return source.project_model
    return _deprecated_model(source)


_warned = set()


def _deprecated_model(source):
    model = getattr(source, 'model', None)
    if model is not None:
        key = type(source)
        if key not in _warned:
            _warned.add(key)
            warnings.warn(
                '%s.%s: djgentelella reads the "model" attribute of a data '
                'source as the model of the project behind it; declare '
                '"project_model" instead (None for a source whose rows are '
                'not rows of a model of the project). "model" stops being '
                'read in a future version.' % (key.__module__, key.__qualname__),
                DeprecationWarning, stacklevel=3)
    return model


@dataclass
class Column:
    """One column a data source exposes.

    ``name`` is the ORM path the queries run on (``'total'``,
    ``'cliente__nombre'``); ``kind`` decides which operators and aggregates
    are allowed on it. ``aggregatable`` defaults to True for numeric kinds.
    """
    name: str
    label: str
    kind: str
    filterable: bool = True
    sortable: bool = True
    aggregatable: bool = None
    choices: list = None
    #: Free hints for the widgets (format, width, ...). Not used by queries.
    extra: dict = dc_field(default_factory=dict)
    #: The size of a ``decimal`` column (a model ``DecimalField``'s): a filter
    #: value with more whole digits than ``max_digits - decimal_places`` is
    #: refused by ``coerce_value``. None: only the generic limits apply.
    max_digits: int = None
    decimal_places: int = None

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError('Unknown column kind %r for %r'
                             % (self.kind, self.name))
        if self.aggregatable is None:
            self.aggregatable = self.kind in NUMERIC_KINDS

    def as_dict(self):
        return {
            'name': self.name, 'label': str(self.label), 'kind': self.kind,
            'filterable': self.filterable, 'sortable': self.sortable,
            'aggregatable': self.aggregatable,
            'choices': ([[value, str(label)] for value, label in self.choices]
                        if self.choices is not None else None),
            'extra': self.extra,
        }


class DataSource:
    """Base class. Subclasses implement :meth:`columns` and
    :meth:`get_queryset`; :meth:`has_permission` checks ``perms``.

    ``perms`` is a list of permission names the user needs all of. ``None``
    (the default) only asks for an authenticated user; an empty list means
    anyone may read the source, anonymous users included, and has to be
    written on purpose.
    """
    name = ''
    label = ''
    #: None: any authenticated user. [] : nobody is checked.
    perms = None
    #: Search engine: 'auto' (full-text on PostgreSQL, icontains elsewhere),
    #: 'fulltext' or 'icontains'.
    search_mode = 'auto'
    #: Text search configuration for SearchVector/SearchQuery ('spanish',
    #: 'simple', ...). None uses the database default.
    search_config = None

    def columns(self, request):
        raise NotImplementedError

    def get_queryset(self, request):
        """The rows ``request`` may read, as a queryset.

        A subclass may take the query parameters too, as
        ``get_queryset(self, request, params=None)``: the query functions
        (:func:`~djgentelella.datasources.query.source_queryset`) then pass
        the parameter document they are about to apply, already normalized
        by ``parse_params`` -- ``None`` when there is none. It is a hint, for
        a source that can narrow what it reads (an external API with filters
        of its own): the queryset may hold more rows than the filters select,
        never fewer, because the filters, the search and the ordering are
        applied on it all the same.

        Building the queryset should not read the rows: ``validate_params``
        builds it to let the ORM check the values, and reading them is the
        job of whoever evaluates it. An error reading them is
        :class:`DataSourceUnavailable`.
        """
        raise NotImplementedError

    @property
    def project_model(self):
        """The model of the project the rows are rows of -- their pks are pks
        of it, so a row link, an edit or a ``pk__in`` reach them -- or None
        (rows read from an external API, computed in Python...).

        A subclass sets it, as a class attribute or a property. Without it,
        a ``model`` attribute is still read, with a ``DeprecationWarning``.
        """
        return _deprecated_model(self)

    def has_permission(self, request):
        if self.perms is not None and not list(self.perms):
            return True
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return False
        return bool(self.perms is None or user.has_perms(list(self.perms)))

    def get_label(self):
        return self.label or self.name

    def column_map(self, request):
        return {column.name: column for column in self.columns(request)}

    def __repr__(self):
        return '<%s %s>' % (type(self).__name__, self.name)


def model_field_kind(model_field):
    """The column kind of a model field."""
    if model_field.many_to_many:
        return 'm2m'
    if model_field.is_relation:
        return 'fk'
    if getattr(model_field, 'choices', None):
        return 'choices'
    if isinstance(model_field, models.BooleanField):
        return 'boolean'
    # DateTimeField is a DateField, so it has to be tested first.
    if isinstance(model_field, models.DateTimeField):
        return 'datetime'
    if isinstance(model_field, models.DateField):
        return 'date'
    if isinstance(model_field, (models.IntegerField, models.AutoField)):
        return 'integer'
    if isinstance(model_field, (models.DecimalField, models.FloatField)):
        return 'decimal'
    if isinstance(model_field, models.JSONField):
        return 'json'
    if isinstance(model_field, models.TextField):
        return 'text'
    return 'string'


def resolve_field_path(model, path):
    """The model field at the end of an ORM path like ``'country__name'``,
    and the verbose names along it."""
    names = []
    current = model
    field = None
    for part in path.split('__'):
        if current is None:
            raise FieldDoesNotExist('%s has no field %r' % (model, path))
        field = current._meta.get_field(part)
        names.append(str(getattr(field, 'verbose_name', part)))
        current = field.related_model if field.is_relation else None
    return field, names


class ModelDataSource(DataSource):
    """A data source over a model, with its columns taken from the fields.

    :param fields: field names or ORM paths (``'country__name'``) to expose;
        by default every concrete field and forward many-to-many.
    :param exclude: names to leave out of the default list.
    :param queryset: base queryset; ``model._default_manager.all()`` if None.
    :param perms: permissions needed; the model's ``view`` permission if None,
        nobody checked if ``[]``.
    :param site_field: field holding the Site; rows are then limited to the
        current Site and the global ones (``site_field`` empty), as the Site
        rule of :mod:`djgentelella.sites` says.
    """

    model = None
    #: None: the model's view permission. [] : nobody is checked.
    perms = None
    fields = None
    exclude = ()
    queryset = None
    site_field = None

    def __init__(self, model=None, *, name=None, label=None, fields=None,
                 exclude=None, queryset=None, perms=None, site_field=None,
                 columns=None):
        # Every argument can also be a class attribute, so a subclass can be
        # registered with ``@register_datasource`` and no arguments.
        self.model = model = model or self.model
        if model is None:
            raise ValueError('ModelDataSource needs a model')
        opts = model._meta
        self.name = name or self.name or opts.label_lower
        self.label = label or self.label or opts.verbose_name_plural
        if fields is not None:
            self.fields = fields
        if exclude is not None:
            self.exclude = tuple(exclude)
        if queryset is not None:
            self.queryset = queryset
        if perms is None:
            perms = self.perms
        if perms is None:
            perms = ['%s.view_%s' % (opts.app_label, opts.model_name)]
        self.perms = list(perms)
        if site_field is not None:
            self.site_field = site_field
        self.extra_columns = {column.name: column for column in columns or ()}

    @property
    def project_model(self):
        return self.model

    def field_names(self):
        if self.fields is not None:
            return list(self.fields)
        opts = self.model._meta
        names = [f.name for f in opts.concrete_fields]
        names += [f.name for f in opts.many_to_many]
        return [name for name in names if name not in self.exclude]

    def column_for(self, path):
        if path in self.extra_columns:
            return self.extra_columns[path]
        model_field, names = resolve_field_path(self.model, path)
        kind = model_field_kind(model_field)
        choices = None
        if kind == 'choices':
            choices = list(model_field.flatchoices)
        label = capfirst(' '.join(names)) if len(names) > 1 else capfirst(names[0])
        return Column(
            name=path, label=label, kind=kind, choices=choices,
            max_digits=getattr(model_field, 'max_digits', None)
            if isinstance(model_field, models.DecimalField) else None,
            decimal_places=getattr(model_field, 'decimal_places', None)
            if isinstance(model_field, models.DecimalField) else None,
            sortable=kind != 'm2m',
            # Summing primary keys says nothing.
            aggregatable=kind in NUMERIC_KINDS and not model_field.primary_key,
            # A file is a path in the database: searchable, never a facet.
            filterable=not isinstance(model_field, models.FileField),
        )

    def columns(self, request):
        result = [self.column_for(name) for name in self.field_names()]
        known = {column.name for column in result}
        result += [column for name, column in self.extra_columns.items()
                   if name not in known]
        return result

    def base_queryset(self, request):
        if self.queryset is not None:
            return self.queryset.all()
        return self.model._default_manager.all()

    def get_queryset(self, request):
        if not self.has_permission(request):
            return self.model._default_manager.none()
        queryset = self.base_queryset(request)
        if self.site_field:
            queryset = queryset.filter(site_q(get_current_site(request),
                                              field=self.site_field))
        return queryset


class FunctionDataSource(DataSource):
    """A data source computed in Python: ``fn(request)`` returns the queryset.

    ``columns`` is a list of :class:`Column` or a callable ``(request) ->
    list[Column]``. ``perms`` works as in :class:`DataSource`: ``None`` (the
    default) asks for an authenticated user, ``[]`` opens it to anyone.

    ``fn`` only runs for a user with permission. For anyone else
    :meth:`get_queryset` returns ``model._default_manager.none()`` when
    ``model`` is given, and raises ``PermissionDenied`` when it is not (the
    API views check the permission first and answer 403 anyway).
    """

    def __init__(self, fn, columns, *, name=None, label=None, perms=None,
                 search_mode=None, model=None):
        self.fn = fn
        self.model = model
        self._columns = columns
        self.name = name or '%s.%s' % (fn.__module__.split('.')[0], fn.__name__)
        self.label = label or self.name
        self.perms = None if perms is None else list(perms)
        if search_mode:
            self.search_mode = search_mode

    @property
    def project_model(self):
        return self.model

    def columns(self, request):
        if callable(self._columns):
            return list(self._columns(request))
        return list(self._columns)

    def get_queryset(self, request):
        if not self.has_permission(request):
            if self.model is not None:
                return self.model._default_manager.none()
            raise PermissionDenied()
        return self.fn(request)


_registry = {}


def register_datasource(source_or_class):
    """Register a data source (an instance, or a class built with no
    arguments). Usable as a class decorator; returns its argument. A name
    registered twice is replaced."""
    source = source_or_class() if isinstance(source_or_class, type) \
        else source_or_class
    if not source.name:
        raise ValueError('A data source needs a name: %r' % source)
    if source.name in _registry:
        logger.debug('Data source %s replaced', source.name)
    _registry[source.name] = source
    return source_or_class


def unregister_datasource(name):
    _registry.pop(name, None)


def autodiscover():
    """Import ``gtdatasources`` from every installed app that has one, once."""
    autodiscover_once('gtdatasources')


def get_datasource(name):
    """The registered data source called ``name``; KeyError if none."""
    if apps.ready:
        # Also when the app is not in INSTALLED_APPS, so ready() never ran.
        autodiscover()
    return _registry[name]


def get_datasources():
    if apps.ready:
        autodiscover()
    return dict(_registry)
