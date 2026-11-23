"""Which Python callables a flow written as JSON may name.

A :class:`~djgentelella.flows.models.FlowDefinition` is data: whoever can
publish one should not be able to make the engine import and call any
function of the project. So in a JSON document a dotted path -- a condition
(``"pkg.fn"`` or ``{"function": "pkg.fn"}``), the ``function`` of a ``call``
action, the ``form`` of a transition -- has to be allowed:

* registered with :func:`register_callable` (or, for conditions, with
  :func:`~djgentelella.flows.conditions.register_condition`); or
* listed in ``GT_FLOWS_ALLOWED_CALLABLES``: exact paths or prefixes
  (``'myapp.flows'`` allows ``myapp.flows.anything``). Empty by default.

A path that is not allowed is an error when the document is published
(:func:`validate_callables`; :func:`validate_actions` checks a list of
actions on its own) and, should a stored document hold one anyway,
an audited failure when it runs: it is logged on ``djgentelella.flows``,
a condition or form blocks its transition (``TransitionBlocked``) and a
``call`` refuses to run (:class:`CallableNotAllowed`), which leaves an
activity in error in the instance log.

Flows declared as Python classes are code, not data: nothing here applies
to them.
"""
import logging

from django.conf import settings
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _

from djgentelella.designs.jsonschema import Error
from djgentelella.flows import conditions
from djgentelella.flows.exceptions import TransitionBlocked, TransitionNotAllowed

logger = logging.getLogger('djgentelella.flows')

#: The name of the ``call`` action (:class:`~djgentelella.flows.actions.
#: CallFunction`), which imports this module to guard its JSON form.
CALL = 'call'

_registry = set()


class CallableNotAllowed(TransitionNotAllowed):
    """A JSON flow names a callable that is not allowed."""


class DocumentError(Error):
    """A problem of a flow document: the
    :class:`~djgentelella.designs.jsonschema.Error` ``(path, message)`` of the
    design documents, whose ``str()`` is ``'path: message'``.

    Transitional compatibility with code that reads these errors as their
    text: the methods of ``str`` that a tuple does not have (``partition``,
    ``startswith``...) answer on the text, ``in`` looks into it and ``==``
    with a ``str`` compares the text. Everything else is the tuple's:
    ``index``, ``count``, ``len()``, indexing, iteration, ``+`` and the hash
    (so an error and its text are not the same set member or dict key). New
    code reads ``error.path`` and ``error.message``; the text side will be
    removed once the consumers do.
    """

    __slots__ = ()

    def __eq__(self, other):
        if isinstance(other, str):
            return str(self) == other
        return super().__eq__(other)

    def __ne__(self, other):
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    __hash__ = Error.__hash__

    def __contains__(self, item):
        if isinstance(item, str) and item in str(self):
            return True
        return super().__contains__(item)

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        return getattr(str(self), name)


def register_callable(obj=None, *, name=None):
    """Allow a function or a form class in JSON flows, by its dotted path
    (or ``name``)::

        @register_callable
        def notify_erp(context): ...
    """
    def decorator(target):
        _registry.add(name or '%s.%s' % (target.__module__, target.__qualname__))
        return target
    return decorator(obj) if obj is not None else decorator


def unregister_callable(path):
    _registry.discard(path)


def _registered_conditions():
    return {'%s.%s' % (getattr(function, '__module__', ''),
                       getattr(function, '__qualname__', ''))
            for function in conditions._registry.values()}


def is_allowed(path):
    """Whether a JSON flow may name the callable at ``path``."""
    if not isinstance(path, str) or not path:
        return False
    if path in _registry or path in conditions._registry:
        return True
    for entry in getattr(settings, 'GT_FLOWS_ALLOWED_CALLABLES', None) or ():
        base = entry.rstrip('*').rstrip('.')
        if base and (path == base or path.startswith(base + '.')):
            return True
    return path in _registered_conditions()


def _refuse(path, where):
    logger.warning('Flow callable not allowed: %r (%s). Register it with '
                   'register_callable() or list it in '
                   'GT_FLOWS_ALLOWED_CALLABLES.', path, where)
    return _('%(path)s is not an allowed callable.') % {'path': path}


def import_allowed(path, where='flow'):
    """``import_string(path)`` for a JSON flow; :class:`CallableNotAllowed`,
    logged, when ``path`` is not allowed."""
    if not is_allowed(path):
        raise CallableNotAllowed(_refuse(path, where))
    return import_string(path)


def _condition_path(spec):
    """The dotted path a condition names, or None (an authorization
    condition dict, a callable)."""
    if isinstance(spec, dict) and set(spec) == {'function'}:
        spec = spec['function']
    return spec if isinstance(spec, str) else None


class GuardedCondition:
    """A condition of a JSON flow that names a callable: checked when it
    runs; one not allowed blocks its transition."""

    def __init__(self, spec, where):
        self.spec = spec
        self.path = _condition_path(spec)
        self.where = where
        self.__name__ = self.path

    def __call__(self, context):
        if not is_allowed(self.path):
            raise TransitionBlocked(_refuse(self.path, self.where))
        return conditions.evaluate(self.spec, context)

    def __str__(self):
        return self.path


class GuardedCall:
    """The ``function`` of a ``call`` action of a JSON flow, checked when it
    runs."""

    def __init__(self, path, where):
        self.path = path
        self.where = where
        self.__name__ = path

    def __call__(self, context):
        return import_allowed(self.path, self.where)(context)

    def __str__(self):
        return self.path


def guard_condition(spec, where):
    """``spec`` as a JSON flow uses it: guarded when it names a callable."""
    if _condition_path(spec) is None:
        return spec
    return GuardedCondition(spec, where)


def guard_action(action, where):
    """``action`` as a JSON flow uses it: a ``call`` checks its function.
    Guarding it again only updates ``where``, the place the log names."""
    if getattr(action, 'name', None) != CALL:
        return action
    function = getattr(action, 'function', None)
    if isinstance(function, GuardedCall):
        function.where = where
    elif isinstance(function, str):
        action.function = GuardedCall(function, where)
    return action


def blocked_form(path, where):
    """The condition of a transition whose form is not allowed: it always
    blocks (and logs)."""
    def blocked(context):
        raise TransitionBlocked(_refuse(path, where))
    blocked.__name__ = path
    return blocked


def _check(path, where, errors):
    if path is not None and not is_allowed(path):
        errors.append(DocumentError(where, _(
            '%(path)s is not an allowed callable (register it with '
            'register_callable or list it in GT_FLOWS_ALLOWED_CALLABLES)')
            % {'path': path}))


def validate_actions(specs, where=''):
    """:class:`~djgentelella.designs.jsonschema.Error` for each ``call``
    action of the list ``specs`` (``{"action": ..., "props": {...}}``) whose
    ``function`` is not allowed, at ``<where>[<index>].props.function``.

    For lists of actions outside a flow document -- an automation's, say --;
    :func:`validate_callables` checks those of a whole document. Only the
    allowlist is checked here: :func:`~djgentelella.flows.actions.
    action_from_json` reports an unknown action or invalid props.
    """
    errors = []
    for index, spec in enumerate(specs if isinstance(specs, list) else ()):
        if isinstance(spec, dict) and spec.get('action') == CALL:
            props = spec.get('props')
            function = props.get('function') if isinstance(props, dict) else None
            _check(function if isinstance(function, str) else None,
                   '%s[%d].props.function' % (where, index), errors)
    return errors


def _check_actions(specs, where, errors):
    errors.extend(validate_actions(specs, where))


def _check_condition(spec, where, errors):
    path = _condition_path(spec)
    if path is not None and path not in conditions._registry:
        _check(path, where, errors)


def validate_callables(document):
    """:class:`~djgentelella.designs.jsonschema.Error` ``(path, message)``
    for each callable ``document`` names that is not allowed: conditions,
    ``call`` actions and transition forms."""
    errors = []
    if not isinstance(document, dict):
        return errors
    for index, spec in enumerate(document.get('transitions') or ()):
        if not isinstance(spec, dict):
            continue
        where = '$.transitions[%d]' % index
        if 'condition' in spec:
            _check_condition(spec['condition'], where + '.condition', errors)
        if isinstance(spec.get('form'), str) and spec['form']:
            _check(spec['form'], where + '.form', errors)
        _check_actions(spec.get('actions'), where + '.actions', errors)
    for index, state in enumerate(document.get('states') or ()):
        if not isinstance(state, dict):
            continue
        where = '$.states[%d]' % index
        for key in ('on_enter', 'on_exit', 'actions'):
            _check_actions(state.get(key), '%s.%s' % (where, key), errors)
        if isinstance(state.get('deadline'), dict):
            _check_actions(state['deadline'].get('actions'),
                           where + '.deadline.actions', errors)
        for number, case in enumerate(state.get('cases') or ()):
            if isinstance(case, dict) and 'condition' in case:
                _check_condition(case['condition'],
                                 '%s.cases[%d].condition' % (where, number), errors)
    for key in ('on_enter', 'on_exit'):
        mapping = document.get(key)
        for state, specs in (mapping.items() if isinstance(mapping, dict) else ()):
            _check_actions(specs, '$.%s.%s' % (key, state), errors)
    deadlines = document.get('deadlines')
    for state, spec in (deadlines.items() if isinstance(deadlines, dict) else ()):
        if isinstance(spec, dict):
            _check_actions(spec.get('actions'), '$.deadlines.%s.actions' % state,
                           errors)
    return errors
