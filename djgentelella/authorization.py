"""Named authorization rules, JSON conditions and feature flags.

**Authorizations** are Python functions with a name, like the "authorization
schemes" of Oracle APEX. They live in ``<app>/gtauth.py``, which is
autodiscovered::

    from djgentelella.authorization import authorization

    @authorization('es_supervisor')
    def es_supervisor(request, obj=None):
        return request.user.groups.filter(name='Supervisores').exists()

The result of each one is cached on the request while it lasts;
``@authorization('name', cache=False)`` turns that off.

A **condition** is JSON, so it can travel in a design node, a menu item, a
column, a button or a flow::

    {"all": [
      {"perm": "ventas.view_pedido"},
      {"auth": "es_supervisor"},
      {"any": [{"group": "Finanzas"}, {"setting": "modo", "equals": "abierto"}]},
      {"not": {"flag": "beta_reportes"}}
    ]}

:func:`validate_condition` lists what is wrong with one, with the path of
each problem; :func:`evaluate_condition` says whether it holds. ``None`` is
"no condition" and always holds; anything invalid never does.

**Feature flags** are :class:`~djgentelella.models.GentelellaSettings` rows
whose key starts with ``flag.``, with the Site rule of
:mod:`djgentelella.sites`: the value of the current Site wins over the global
one.

The module can be imported before the app registry is ready (from a settings
module or another app's ``AppConfig``): models, ``auth.mixins`` and
``djgentelella.utils`` are looked up when they are used, and
``ConditionRequiredMixin`` lives in :mod:`djgentelella.views.conditions`,
imported on first access.
"""

import json
import logging
import re
from functools import wraps

from django.apps import apps
from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.db.models import Model
from django.http import QueryDict
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _
from rest_framework.permissions import BasePermission

from djgentelella.autodiscover import autodiscover_once
from djgentelella.designs.jsonschema import Error
from djgentelella.sites import get_current_site, resolve_site, site_pk

logger = logging.getLogger(__name__)

__all__ = [
    'ConditionPermission', 'ConditionRequest', 'ConditionRequiredMixin',
    'Error', 'FLAG_PREFIX', 'SAFE_USER_ATTRS', 'authorization',
    'autodiscover', 'check_authorization', 'condition_required',
    'evaluate_condition', 'flag_enabled', 'flag_names', 'get_authorizations',
    'parse_condition', 'set_flag', 'site_groups', 'validate_condition',
]

#: The settings key of the flag ``name`` is ``FLAG_PREFIX + name``.
FLAG_PREFIX = 'flag.'
#: What a flag name may be made of; the settings key has 100 characters.
FLAG_NAME = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,94}$')
#: Values of a setting that mean "on".
TRUE_VALUES = frozenset(('1', 'true', 'yes', 'on'))
#: The user attributes a ``user_attr`` node may read. Nothing else: a
#: condition is data, and could otherwise probe any attribute of the user.
SAFE_USER_ATTRS = ('is_authenticated', 'is_staff', 'is_superuser')
#: How deep ``all``/``any``/``not`` may nest.
MAX_DEPTH = 32

PERMISSION = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z0-9_\-]+$')
#: The node types and the keys each one takes besides its own.
NODES = {
    'perm': (), 'auth': (), 'group': (), 'setting': ('equals', 'in'),
    'flag': (), 'user_attr': (), 'all': (), 'any': (), 'not': (),
}

# Where the per-request caches live.
_AUTH_CACHE_ATTR = '_gt_authorization_cache'
_GROUPS_CACHE_ATTR = '_gt_site_groups_cache'

_registry = {}


# -- what needs the app registry ----------------------------------------------------
# Imported or looked up on use, so the module itself loads before the registry is
# ready: django.contrib.auth.models and djgentelella.utils import models.

def _anonymous_user():
    from django.contrib.auth.models import AnonymousUser  # noqa: PLC0415 -- early import

    return AnonymousUser()


def _settings_model():
    return apps.get_model('djgentelella', 'GentelellaSettings')


def _get_settings(key, site):
    from djgentelella.utils import get_settings  # noqa: PLC0415 -- early import

    return get_settings(key, site=site, none_asdefault=True)


def __getattr__(name):
    # ConditionRequiredMixin subclasses AccessMixin, whose module imports the
    # auth models: it is imported the first time someone asks for it.
    if name == 'ConditionRequiredMixin':
        from djgentelella.views.conditions import (  # noqa: PLC0415 -- early import
            ConditionRequiredMixin,
        )
        return ConditionRequiredMixin
    raise AttributeError('module %r has no attribute %r' % (__name__, name))


# -- authorizations -------------------------------------------------------------

def authorization(name, *, cache=True):
    """Register ``fn(request, obj=None) -> bool`` as the authorization ``name``.

    A second function with the same name replaces the first. With
    ``cache=False`` the function runs on every check, instead of once per
    request (and object).
    """
    if not isinstance(name, str) or not name:
        raise ImproperlyConfigured('An authorization needs a name, not %r.' % (name,))

    def decorator(function):
        _registry[name] = (function, cache)
        return function
    return decorator


def autodiscover():
    """Import ``gtauth.py`` of every installed app (once)."""
    autodiscover_once('gtauth')


def get_authorizations():
    """``{name: function}`` of the registered authorizations."""
    autodiscover()
    return {name: entry[0] for name, entry in _registry.items()}


def _obj_key(obj):
    """What identifies ``obj`` in the per-request cache, or ``None`` when it
    cannot be cached (an object that is not a saved row)."""
    if obj is None:
        return ()
    if isinstance(obj, Model) and obj.pk is not None:
        return (obj._meta.label_lower, obj.pk)
    return None


def _user_of(request):
    user = getattr(request, 'user', None)
    return user if user is not None else _anonymous_user()


def _request_cache(request, attr):
    if request is None:
        return None
    cache = getattr(request, attr, None)
    if cache is None:
        cache = {}
        try:
            setattr(request, attr, cache)
        except AttributeError:
            return None
    return cache


def check_authorization(name, request, obj=None):
    """Whether the authorization ``name`` holds for ``request`` (and ``obj``).

    An unknown name is ``False`` and is logged, as is a function that raises:
    a broken rule closes, it does not open.
    """
    autodiscover()
    entry = _registry.get(name)
    if entry is None:
        logger.error('Unknown authorization %r: register it with '
                     '@authorization(%r) in a gtauth.py.', name, name)
        return False
    function, use_cache = entry
    key = None
    cache = None
    if use_cache:
        obj_key = _obj_key(obj)
        if obj_key is not None:
            user = _user_of(request)
            key = (name, getattr(user, 'pk', None), obj_key)
            cache = _request_cache(request, _AUTH_CACHE_ATTR)
            if cache is not None and key in cache:
                return cache[key]
    try:
        result = bool(function(request, obj))
    except PermissionDenied:
        result = False
    except Exception:
        logger.exception('Authorization %r failed; it counts as not granted.', name)
        result = False
    if cache is not None:
        cache[key] = result
    return result


class ConditionRequest:
    """A stand-in for the request when a condition is evaluated outside one.

    It is the public way to evaluate conditions, authorizations and flags *on
    behalf of* someone when there is no request -- a background job, a timer,
    an automation, a management command::

        request = ConditionRequest(user=automation.run_as, site=automation.site)
        if evaluate_condition(cond, request, obj):
            ...

    ``user`` is who the condition is evaluated for: ``None`` is the system,
    which counts as an anonymous user (so ``perm``, ``group`` and
    ``user_attr`` are false for it). ``site`` is the Site whose scope applies
    (settings, flags, groups by Site): a ``Site``, its id, or ``None`` for the
    global scope -- give the Site of the job, or Site rules silently fall back
    to the global values. An id of no Site raises ``ValueError``: it is never
    taken as the global scope.

    It has what authorization functions usually read of a request:
    ``user``, ``site``, an empty ``GET``/``POST``/``COOKIES``/``META``,
    ``method = None`` and ``path = ''``. Per-request caches (authorizations
    with ``cache=True``) live on it, so reuse one object for many rows of the
    same user and build a new one when the user or the data change.
    """

    #: Tells it apart from a real request.
    is_condition_request = True
    method = None
    path = ''
    path_info = ''

    def __init__(self, user=None, site=None):
        self.user = user if user is not None else _anonymous_user()
        # get_current_site() takes request.site as it is, so a Site id is
        # turned into the Site here.
        self.site = self._site(site)
        self.GET = QueryDict()
        self.POST = QueryDict()
        self.COOKIES = {}
        self.META = {}

    @staticmethod
    def _site(site):
        return resolve_site(site)

    def __repr__(self):
        return '<ConditionRequest user=%r site=%r>' % (self.user, self.site)


# -- groups by Site -----------------------------------------------------------------

def default_site_groups(user, site):
    """Every group of ``user``, whatever the Site (the default resolver)."""
    if user is None or not user.is_authenticated:
        return apps.get_model('auth', 'Group').objects.none()
    return user.groups.all()


def _site_groups_resolver():
    path = getattr(settings, 'GT_SITE_GROUPS_RESOLVER', None)
    if not path:
        return default_site_groups
    if callable(path):
        return path
    return import_string(path)


def site_groups(user, site):
    """The groups of ``user`` that count on ``site`` (``None`` is global).

    The extension point of roles by Site: ``GT_SITE_GROUPS_RESOLVER`` is the
    dotted path of a ``function(user, site)`` returning groups (a queryset or
    any iterable of ``Group``). By default, all the groups of the user.
    """
    return _site_groups_resolver()(user, site)


def _group_names(request, user, site):
    cache = _request_cache(request, _GROUPS_CACHE_ATTR)
    key = (getattr(user, 'pk', None), site_pk(site))
    if cache is not None and key in cache:
        return cache[key]
    names = frozenset(group.name for group in site_groups(user, site))
    if cache is not None:
        cache[key] = names
    return names


# -- feature flags ---------------------------------------------------------------------

def _flag_key(name):
    if not isinstance(name, str) or not FLAG_NAME.match(name):
        raise ValueError('%r is not a valid flag name (letters, digits, "_", '
                         '"-" and ".", up to 95 characters).' % (name,))
    return FLAG_PREFIX + name


def _truthy(value):
    return isinstance(value, str) and value.strip().lower() in TRUE_VALUES


def flag_value(name, site=None):
    """``True``/``False`` as stored for ``site`` (or global), or ``None`` when
    nothing is stored there: the raw state, without the fallback."""
    row = _settings_model().objects.filter(
        key=_flag_key(name), site_id=site_pk(site)).values_list(
        'value', flat=True).first()
    return None if row is None else _truthy(row)


def flag_enabled(name, request=None, *, site=None):
    """Whether the flag ``name`` is on for the Site of ``request``.

    The Site's value wins over the global one; without either the flag
    is off. ``site`` is used instead of the request's when given.
    """
    if site is None:
        site = get_current_site(request)
    return _truthy(_get_settings(_flag_key(name), site))


def set_flag(name, value, site=None):
    """Turn the flag ``name`` on or off, globally or for ``site``.

    ``value=None`` removes the value stored in that scope: a Site then
    follows the global value again.
    """
    key = _flag_key(name)
    if value is None:
        # A delete through the ORM: the post_delete signal forgets the cache.
        for row in _settings_model().objects.filter(key=key,
                                                    site_id=site_pk(site)):
            row.delete()
        return
    from djgentelella.utils import set_settings  # noqa: PLC0415 -- early import

    set_settings(key, 'true' if value else 'false', site=site)


def flag_names():
    """The names of every flag stored, in any scope, sorted."""
    keys = _settings_model().objects.filter(
        key__startswith=FLAG_PREFIX).values_list('key', flat=True).distinct()
    # A row written by hand with a key no flag can have is not one.
    return sorted({key[len(FLAG_PREFIX):] for key in keys
                   if FLAG_NAME.match(key[len(FLAG_PREFIX):])})


# -- conditions ---------------------------------------------------------------------

def parse_condition(value):
    """A condition from a template or a form: a dict, ``None``, or JSON text."""
    if value is None or value == '':
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value  # validate_condition says why it is not one
    return value


def _string_list(value):
    """``value`` as a list of non-empty strings, or ``None``."""
    items = [value] if isinstance(value, str) else value
    if not isinstance(items, list) or not items:
        return None
    if not all(isinstance(item, str) and item for item in items):
        return None
    return items


def _node_type(cond):
    found = [key for key in cond if key in NODES]
    return found[0] if len(found) == 1 else None


def validate_condition(cond, path='$', *, check_names=True):
    """The :class:`~djgentelella.designs.jsonschema.Error` list of ``cond``.

    Empty means valid. ``None`` is valid (no condition). ``check_names``
    also checks that each ``auth`` is a registered authorization: an unknown
    one is an error when saving, and only ``False`` (and a log) when
    evaluating.
    """
    if cond is None:
        return []
    errors = []
    _validate(cond, path, 0, errors, check_names)
    return errors


def _validate(cond, path, depth, errors, check_names):
    if depth > MAX_DEPTH:
        errors.append(Error(path, _('conditions nest at most %d levels') % MAX_DEPTH))
        return
    if not isinstance(cond, dict):
        errors.append(Error(path, _('a condition must be an object, not %s')
                            % type(cond).__name__))
        return
    kind = _node_type(cond)
    if kind is None:
        if not cond:
            errors.append(Error(path, _('empty condition')))
        else:
            errors.append(Error(path, _('a condition has exactly one of %(nodes)s; '
                                        'got %(keys)s') % {
                'nodes': ', '.join(NODES), 'keys': ', '.join(sorted(map(str, cond)))}))
        return
    extra = sorted(set(cond) - {kind} - set(NODES[kind]))
    if extra:
        errors.append(Error(path, _('unexpected key(s) in a %(kind)r condition: '
                                    '%(keys)s') % {
            'kind': kind, 'keys': ', '.join(map(str, extra))}))
    value = cond[kind]
    here = '%s.%s' % (path, kind)
    if kind in ('all', 'any'):
        if not isinstance(value, list):
            errors.append(Error(here, _('must be a list of conditions')))
            return
        for index, item in enumerate(value):
            _validate(item, '%s[%d]' % (here, index), depth + 1, errors, check_names)
    elif kind == 'not':
        _validate(value, here, depth + 1, errors, check_names)
    elif kind == 'perm':
        perms = _string_list(value)
        if perms is None:
            errors.append(Error(here, _('must be "app.codename" or a non-empty '
                                        'list of them')))
        else:
            for perm in perms:
                if not PERMISSION.match(perm):
                    errors.append(Error(here, _('%r is not an "app.codename" '
                                                'permission') % (perm,)))
    elif kind == 'group':
        if _string_list(value) is None:
            errors.append(Error(here, _('must be a group name or a non-empty '
                                        'list of them')))
    elif kind == 'auth':
        if not isinstance(value, str) or not value:
            errors.append(Error(here, _('must be the name of an authorization')))
        elif check_names and value not in get_authorizations():
            errors.append(Error(here, _('unknown authorization %r') % (value,)))
    elif kind == 'flag':
        if not isinstance(value, str) or not FLAG_NAME.match(value):
            errors.append(Error(here, _('must be a flag name')))
    elif kind == 'user_attr':
        if value not in SAFE_USER_ATTRS:
            errors.append(Error(here, _('must be one of %s')
                                % ', '.join(SAFE_USER_ATTRS)))
    elif kind == 'setting':
        if not isinstance(value, str) or not value or len(value) > 100:
            errors.append(Error(here, _('must be the key of a setting')))
        operators = [op for op in ('equals', 'in') if op in cond]
        if len(operators) != 1:
            errors.append(Error(path, _('a "setting" condition takes "equals" or '
                                        '"in" (one of them)')))
        elif operators == ['equals'] and not _scalar(cond['equals']):
            errors.append(Error(path + '.equals', _('must be a string, a number '
                                                    'or a boolean')))
        elif operators == ['in'] and not (
                isinstance(cond['in'], list)
                and all(_scalar(item) for item in cond['in'])):
            errors.append(Error(path + '.in', _('must be a list of strings, '
                                                'numbers or booleans')))


def _scalar(value):
    return isinstance(value, (str, int, float, bool))


def _as_setting_text(value):
    """How a value compares with a stored setting, which is always text."""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


def _setting_matches(stored, expected):
    if isinstance(expected, bool):
        return (stored or '').strip().lower() == _as_setting_text(expected)
    return stored == _as_setting_text(expected)


class _Unfrozen(Exception):
    """A value :func:`_freeze` does not turn into a cache key."""


def _freeze(value, depth=0):
    """A hashable key for ``value`` that keeps its JSON types apart (a list
    is not a tuple, ``True`` is not ``1``), so a cached validation answers
    exactly what validating it again would."""
    if depth > MAX_DEPTH + 2:
        raise _Unfrozen
    if isinstance(value, dict):
        items = [(_freeze(key, depth + 1), _freeze(item, depth + 1))
                 for key, item in value.items()]
        return (dict, tuple(sorted(items, key=repr)))
    if isinstance(value, list):
        return (list, tuple(_freeze(item, depth + 1) for item in value))
    if value is None or isinstance(value, (str, int, float, bool)):
        return (type(value), value)
    raise _Unfrozen


#: ``_freeze(cond)`` -> the errors of its structure; cleared when it fills.
_structure_cache = {}
_STRUCTURE_CACHE_SIZE = 1024


def _structure_errors(cond):
    """``validate_condition(cond, check_names=False)``, remembered: the
    structure of a condition does not change between evaluations, and
    designs, menus, columns and endpoints evaluate the same ones on every
    request. Names are not checked here, so the registry does not matter."""
    try:
        key = _freeze(cond)
    except _Unfrozen:
        return validate_condition(cond, check_names=False)
    errors = _structure_cache.get(key)
    if errors is None:
        errors = tuple(validate_condition(cond, check_names=False))
        if len(_structure_cache) >= _STRUCTURE_CACHE_SIZE:
            _structure_cache.clear()
        _structure_cache[key] = errors
    return list(errors)


def evaluate_condition(cond, request, obj=None):
    """Whether ``cond`` holds for ``request`` (and ``obj``).

    ``None`` holds. An invalid condition does not, and is logged: a
    condition that cannot be read hides, it does not show. ``request`` may be
    a :class:`ConditionRequest` outside a request, or ``None`` (an anonymous
    user, global scope).
    """
    if cond is None:
        return True
    errors = _structure_errors(cond)
    if errors:
        logger.error('Invalid condition %r: %s', cond,
                     '; '.join(str(error) for error in errors))
        return False
    user = _user_of(request)
    site = get_current_site(request)
    return _evaluate(cond, request, obj, user, site)


def _evaluate(cond, request, obj, user, site):
    kind = _node_type(cond)
    value = cond[kind]
    if kind == 'all':
        return all(_evaluate(item, request, obj, user, site) for item in value)
    if kind == 'any':
        return any(_evaluate(item, request, obj, user, site) for item in value)
    if kind == 'not':
        return not _evaluate(value, request, obj, user, site)
    if kind == 'perm':
        perms = _string_list(value)
        if user.has_perms(perms):
            return True
        # Object permissions (django-guardian & co.): ModelBackend says no to
        # any object, so this only adds.
        return obj is not None and user.has_perms(perms, obj)
    if kind == 'auth':
        return check_authorization(value, request, obj)
    if kind == 'group':
        if not user.is_authenticated:
            return False
        names = _group_names(request, user, site)
        return any(name in names for name in _string_list(value))
    if kind == 'flag':
        return flag_enabled(value, site=site)
    if kind == 'user_attr':
        return bool(getattr(user, value, False))
    if kind == 'setting':
        stored = _get_settings(value, site)
        if stored is None:
            return False
        if 'equals' in cond:
            return _setting_matches(stored, cond['equals'])
        return any(_setting_matches(stored, item) for item in cond['in'])
    return False  # pragma: no cover -- validate_condition refused it


# -- views ------------------------------------------------------------------------

class ConditionPermission(BasePermission):
    """A DRF permission from a condition of the view.

    The view declares ``condition = {...}`` for every action, or
    ``conditions_by_action = {'list': {...}, 'create': {...}}``; an action
    missing from that map is refused, and so is a view that declares neither.
    The condition is evaluated without an object for the view, and again with
    the object in ``has_object_permission``.
    """

    def _condition(self, request, view):
        by_action = getattr(view, 'conditions_by_action', None)
        if by_action is not None:
            action = getattr(view, 'action', None)
            if action is None:
                # A plain APIView: the HTTP method, lowercase.
                action = request.method.lower() if request.method else None
            if action not in by_action:
                return False, None
            return True, by_action[action]
        if hasattr(view, 'condition'):
            return True, view.condition
        return False, None

    def has_permission(self, request, view):
        declared, cond = self._condition(request, view)
        return declared and evaluate_condition(cond, request)

    def has_object_permission(self, request, view, obj):
        declared, cond = self._condition(request, view)
        return declared and evaluate_condition(cond, request, obj)


def condition_required(cond, login_url=None, redirect_field_name=REDIRECT_FIELD_NAME,
                       raise_exception=False):
    """Decorator of a function view that needs ``cond`` to hold.

    Like ``permission_required``: an anonymous user goes to the login page, a
    signed-in one gets a 403. ``raise_exception`` gives the 403 to everyone.
    """
    errors = validate_condition(cond, check_names=False)
    if errors:
        raise ImproperlyConfigured('Invalid condition: ' + '; '.join(map(str, errors)))

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if evaluate_condition(cond, request):
                return view(request, *args, **kwargs)
            if raise_exception or _user_of(request).is_authenticated:
                raise PermissionDenied
            # auth.views imports the auth models: see the top of the module.
            from django.contrib.auth.views import (  # noqa: PLC0415 -- early import
                redirect_to_login,
            )
            return redirect_to_login(request.get_full_path(), login_url,
                                     redirect_field_name)
        return wrapped
    return decorator
