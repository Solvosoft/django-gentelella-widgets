"""Lists of values (LOVs): named option lists, optionally cascading.

A LOV is a function registered under a name. It receives the request, the
values of the fields it depends on and the search text, and returns a queryset
or a list of ``(value, label)``. The value of a queryset of models is the pk;
of a ``values_list('code', 'name')`` (or ``values()``), its first column::

    # myapp/gtlovs.py -- discovered in every app of INSTALLED_APPS
    from djgentelella.lov import register_lov

    @register_lov('provincias', depends_on=['pais'])
    def provincias(request, pais=None, q=''):
        return Provincia.objects.filter(pais=pais, nombre__icontains=q)

It is served as json at ``gtapis/lov/<name>/?q=&page=&pais=`` (the select2
format), edited with ``LOVSelect`` / ``LOVSelectMultiple`` and validated with
``LOVChoiceField``, which checks the value against the LOV computed with the
parent values the form received.

``request`` is None when the LOV is evaluated outside a request: while a field
is validated or its selected label is rendered, unless the form has a
``request`` attribute.

Parent values come from the browser, so they can be anything: when building or
running the queryset raises ``ValueError``, ``TypeError``, ``OverflowError`` or
``ValidationError`` (``?pais=abc`` against an integer foreign key) the LOV is
treated as empty -- the endpoint answers no options and the field rejects the
value -- instead of failing with a 500.
"""

from django.core.exceptions import FieldError, ImproperlyConfigured, ValidationError
from django.db.models import Model, QuerySet
from django.db.models.query import ModelIterable

from djgentelella.autodiscover import autodiscover_once

# What a filter built from a malformed parent value raises.
INVALID_VALUE_ERRORS = (ValueError, TypeError, OverflowError, ValidationError)

_registry = {}


class LOV:
    def __init__(self, name, func, depends_on=(), perms=(), login_required=True,
                 page_size=20):
        if isinstance(depends_on, str) or isinstance(perms, str):
            raise ImproperlyConfigured(
                'register_lov(%r): depends_on and perms are lists' % name)
        self.name = name
        self.func = func
        self.depends_on = list(depends_on)
        self.perms = list(perms)
        self.login_required = login_required
        self.page_size = page_size

    def __repr__(self):
        return '<LOV %s depends_on=%r>' % (self.name, self.depends_on)

    def has_permission(self, request):
        user = getattr(request, 'user', None)
        if self.login_required or self.perms:
            if user is None or not user.is_authenticated:
                return False
        if self.perms and not user.has_perms(self.perms):
            return False
        return True

    def parents(self, values):
        """``values`` reduced to the parents this LOV declares, None if empty."""
        values = values or {}
        result = {}
        for name in self.depends_on:
            value = values.get(name)
            result[name] = None if value in ('', None) else value
        return result

    def evaluate(self, request, parents=None, q=''):
        return self.func(request, q=q or '', **self.parents(parents))

    def page(self, request, parents=None, q='', page=1):
        """One page of ``[(value, label)]`` and whether there are more."""
        start = (page - 1) * self.page_size
        stop = start + self.page_size
        try:
            result = self.evaluate(request, parents, q)
            if isinstance(result, QuerySet):
                rows = list(result[start:stop + 1])
            else:
                rows = list(result)[start:stop + 1]
        except INVALID_VALUE_ERRORS:
            return [], False
        more = len(rows) > self.page_size
        return [_pair(row) for row in rows[:self.page_size]], more

    def find(self, value, parents=None, request=None):
        """``(value, label)`` of ``value`` in the LOV, or None if it is not in."""
        if value in ('', None):
            return None
        try:
            result = self.evaluate(request, parents, '')
            if isinstance(result, QuerySet):
                found = _filter_value(result, value)
                if found is not None:
                    row = found.first()
                    return None if row is None else _pair(row)
            for row in result:
                pair = _pair(row)
                if str(pair[0]) == str(value):
                    return pair
        except INVALID_VALUE_ERRORS:
            return None
        return None

    def contains(self, value, parents=None, request=None):
        return self.find(value, parents, request) is not None

    def label(self, value, parents=None, request=None):
        pair = self.find(value, parents, request)
        return None if pair is None else pair[1]


def _filter_value(queryset, value):
    """``queryset`` reduced to the row whose option value is ``value``, the
    same value :meth:`LOV.page` offers: the pk of a queryset of models, the
    first column of a ``values_list()`` or ``values()``. None when that column
    cannot be filtered on; the rows are compared one by one then."""
    if issubclass(queryset._iterable_class, ModelIterable):
        return queryset.filter(pk=value)
    column = next(iter(queryset.query.selected or ()), None)
    if column is None:
        return None
    try:
        return queryset.filter(**{column: value})
    except FieldError:
        return None


def _pair(row):
    if isinstance(row, Model):
        return row.pk, str(row)
    if isinstance(row, dict):  # a values() queryset: its first two columns
        row = tuple(row.values())
    if isinstance(row, (list, tuple)) and len(row) == 2:
        return row[0], str(row[1])
    return row, str(row)


def register_lov(name, depends_on=(), perms=(), login_required=True, page_size=20):
    """Register the decorated function as the LOV ``name``.

    ``perms`` are checked with ``user.has_perms``; ``login_required=False``
    opens a LOV without perms to anonymous users. A repeated name replaces the
    previous LOV.
    """
    if not isinstance(name, str) or not name or '/' in name:
        raise ImproperlyConfigured('A LOV name is a non empty string without /')

    def decorator(func):
        _registry[name] = LOV(name, func, depends_on=depends_on, perms=perms,
                              login_required=login_required, page_size=page_size)
        return func
    return decorator


def autodiscover():
    """Import ``gtlovs`` from every installed app, once."""
    autodiscover_once('gtlovs')


def get_lov(name):
    """The LOV registered as ``name``; LookupError if there is none."""
    if name not in _registry:
        autodiscover()
    try:
        return _registry[name]
    except KeyError:
        raise LookupError('No LOV registered as %r' % name) from None


def get_lovs():
    autodiscover()
    return dict(_registry)


def unregister_lov(name):
    _registry.pop(name, None)
