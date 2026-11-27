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

The labels can be translated without ``.po`` files (C20): a
``LOVTranslation`` row (LOV, value, language, label) replaces the label of
that value while its language is active (:func:`djgentelella.translations.pick`).
A LOV whose options depend on its parents can give ``all_values``, a function
of the request returning every ``(value, label)``, so the translation screen
can list them; otherwise it lists what the LOV returns without parents.
"""

import logging

from django.apps import apps
from django.core.exceptions import FieldError, ImproperlyConfigured, ValidationError
from django.db.models import Model, QuerySet
from django.db.models.query import ModelIterable

from djgentelella import translations
from djgentelella.autodiscover import autodiscover_once

logger = logging.getLogger(__name__)

# What a filter built from a malformed parent value raises.
INVALID_VALUE_ERRORS = (ValueError, TypeError, OverflowError, ValidationError)

_registry = {}


class LOV:
    def __init__(self, name, func, depends_on=(), perms=(), login_required=True,
                 page_size=20, all_values=None, owner=''):
        if isinstance(depends_on, str) or isinstance(perms, str):
            raise ImproperlyConfigured(
                'register_lov(%r): depends_on and perms are lists' % name)
        self.name = name
        self.func = func
        self.depends_on = list(depends_on)
        self.perms = list(perms)
        self.login_required = login_required
        self.page_size = page_size
        self.all_values = all_values
        #: Who registered it (``'djodo.app.<slug>'``...): a label to list
        #: the LOVs of one owner, with no effect on permissions or the Site.
        self.owner = owner or ''

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
        return self.translate([_pair(row) for row in rows[:self.page_size]]), more

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
                    return None if row is None else self.translate([_pair(row)])[0]
            for row in result:
                pair = _pair(row)
                if str(pair[0]) == str(value):
                    return self.translate([pair])[0]
        except INVALID_VALUE_ERRORS:
            return None
        return None

    def translate(self, pairs, language=None):
        """``pairs`` (``[(value, label)]``) with the labels in ``language``
        (by default the active one) where a ``LOVTranslation`` has one."""
        if not pairs:
            return pairs
        codes = translations.candidates(language)
        rows = apps.get_model('djgentelella', 'LOVTranslation').objects.filter(
            lov=self.name, language__in=codes,
            value__in={str(value) for value, _label in pairs}).values_list(
            'value', 'language', 'label')
        found = {}
        for value, code, label in rows:
            found.setdefault(value, {})[code] = label
        if not found:
            return pairs
        return [(value, translations.pick(found.get(str(value)), label, language))
                for value, label in pairs]

    def values(self, request=None, limit=1000):
        """Every ``(value, label)`` of the LOV with its own labels, at most
        ``limit``: ``all_values(request)`` when it was given, else what it
        returns without parents. The translation screen lists them."""
        try:
            if self.all_values is not None:
                result = self.all_values(request)
            else:
                result = self.evaluate(request, {}, '')
            rows = list(result[:limit]) if isinstance(result, QuerySet) else \
                list(result)[:limit]
        except Exception:
            # A LOV that needs its parents, or a request, to answer: the
            # translation screen lists only what was already translated.
            logger.warning('LOV %s cannot list its values without parents',
                           self.name, exc_info=True)
            return []
        return [_pair(row) for row in rows]

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


def register_lov(name, depends_on=(), perms=(), login_required=True, page_size=20,
                 all_values=None, owner=''):
    """Register the decorated function as the LOV ``name``.

    ``perms`` are checked with ``user.has_perms``; ``login_required=False``
    opens a LOV without perms to anonymous users. A repeated name replaces the
    previous LOV. ``all_values(request)`` returns every option regardless of
    the parents, for the translation screen. ``owner`` is a free label of who
    registered it (``get_lovs(owner=...)`` lists them), like the ``tags`` of a
    pipeline process: it changes neither the permissions nor the Site.
    """
    if not isinstance(name, str) or not name or '/' in name:
        raise ImproperlyConfigured('A LOV name is a non empty string without /')

    def decorator(func):
        _registry[name] = LOV(name, func, depends_on=depends_on, perms=perms,
                              login_required=login_required, page_size=page_size,
                              all_values=all_values, owner=owner)
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


def get_lovs(owner=None):
    """``{name: LOV}``; only those of ``owner`` when given."""
    autodiscover()
    if owner is None:
        return dict(_registry)
    return {name: lov for name, lov in _registry.items() if lov.owner == owner}


def unregister_lov(name):
    _registry.pop(name, None)
