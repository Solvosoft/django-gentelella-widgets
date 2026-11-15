"""Conditions of transitions and ``switch`` cases.

A condition is called with the :class:`~djgentelella.flows.actions.ActionContext`
of the run -- ``context.obj``, ``context.user`` (``None`` for the system),
``context.variables``, ``context.data`` -- and returns true or false, or raises
:class:`~djgentelella.flows.exceptions.TransitionBlocked` to say why not.

It can be given as:

* a callable;
* the name of a function registered with :func:`register_condition`, or a
  dotted path to one (``"app.module.function"``);
* in JSON, ``{"function": "<name or path>"}``;
* any other dict is a condition of :mod:`djgentelella.authorization`
  (``{"perm": ...}``, ``{"all": [...]}``...). It is evaluated for
  ``context.request`` when there is one; otherwise for ``context.user`` (an
  anonymous user for the system) on ``context.site``, through a
  :class:`~djgentelella.authorization.ConditionRequest`.
"""

from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from djgentelella.authorization import (
    ConditionRequest,
    evaluate_condition,
    validate_condition,
)

_registry = {}


def register_condition(name=None):
    """Register a condition function under ``name`` (its dotted path when
    omitted), for flows that name it from JSON::

        @register_condition('expenses.is_high')
        def is_high(context):
            return context.obj.amount >= 1000
    """
    def decorator(function):
        _registry[name or '%s.%s' % (function.__module__, function.__qualname__)] = \
            function
        return function
    if callable(name):  # used bare: @register_condition
        function, name = name, None
        return decorator(function)
    return decorator


def get_conditions():
    """``{name: function}`` of the registered conditions."""
    return dict(_registry)


def get_condition(name):
    if name in _registry:
        return _registry[name]
    try:
        return import_string(name)
    except ImportError:
        raise ImproperlyConfigured('No condition named %r: register it with '
                                   'register_condition()' % name) from None


def compile_condition(spec):
    """``spec`` as a callable ``(context) -> bool``; None stays None."""
    if spec is None or callable(spec):
        return spec
    if isinstance(spec, str):
        return get_condition(spec)
    if isinstance(spec, dict) and set(spec) == {'function'}:
        return get_condition(spec['function'])
    if isinstance(spec, dict):
        def condition(context):
            return evaluate_condition(spec, condition_request(context), context.obj)
        return condition
    raise ImproperlyConfigured('A condition is a callable, a name or a dict, not %r'
                               % (spec,))


def condition_request(context):
    """The request a condition of :mod:`djgentelella.authorization` is
    evaluated for in ``context``."""
    if context.request is not None:
        return context.request
    return ConditionRequest(user=context.user, site=context.site)


def check_condition(spec, path):
    """``"<path>: <problem>"`` strings for a condition of a JSON flow.

    Only the dicts of :mod:`djgentelella.authorization` are checked here,
    unknown authorizations included; names and ``{"function": ...}`` are
    resolved when the flow runs.
    """
    if isinstance(spec, dict) and set(spec) != {'function'}:
        return [str(error) for error in validate_condition(spec, path)]
    return []


def evaluate(spec, context):
    """Whether condition ``spec`` holds in ``context`` (no condition: yes)."""
    condition = compile_condition(spec)
    return True if condition is None else bool(condition(context))
