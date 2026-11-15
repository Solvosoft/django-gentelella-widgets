"""Forms of human tasks: what the person fills in when completing one.

A ``human_task`` activity names its form, and the task page shows it next to
the outcome buttons, validates it and passes its ``cleaned_data`` to
:meth:`Task.complete <djgentelella.flows.models.Task.complete>`, so it ends
up in the instance ``variables``::

    from djgentelella.flows import register_task_form

    @register_task_form('expenses.review')
    class ReviewForm(GTForm):
        amount = forms.DecimalField()
        note = forms.CharField(required=False)

and, in a JSON flow, ``{"type": "human_task", ..., "form": "expenses.review"}``
(a class in ``gtflows.py`` may pass ``form=ReviewForm`` itself).

A form is named by its registered name -- the class's dotted path when the
decorator gets no name -- or by a dotted path that the flow allowlist permits
(``GT_FLOWS_ALLOWED_CALLABLES`` or :func:`~djgentelella.flows.callables.
register_callable`, see :mod:`djgentelella.flows.callables`). Nothing else is
found: a flow published as JSON cannot make the engine import an arbitrary
path. :func:`get_task_form` is the one place a name becomes a class.

A JSON document that names a form which is neither is refused when it is
published (:func:`validate_task_forms`); a stored one still loads, and its
``human_task`` refuses to create the task when the flow reaches it
(:class:`BlockedTaskForm`): the activity is left in error, logged.
"""

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from djgentelella.flows.callables import CallableNotAllowed, _refuse, is_allowed

_registry = {}


def form_path(form_class):
    return '%s.%s' % (form_class.__module__, form_class.__qualname__)


def register_task_form(name=None):
    """Register a form class for human tasks under ``name`` (its dotted path
    when omitted). Usable as ``@register_task_form``,
    ``@register_task_form('name')`` or ``register_task_form('name')(cls)``.
    A name registered again is replaced."""
    def decorator(form_class):
        if not (isinstance(form_class, type)
                and issubclass(form_class, forms.BaseForm)):
            raise ImproperlyConfigured('%r is not a form class' % (form_class,))
        _registry[name or form_path(form_class)] = form_class
        return form_class
    if isinstance(name, type):  # used bare: @register_task_form
        form_class, name = name, None
        return decorator(form_class)
    return decorator


def unregister_task_form(name):
    _registry.pop(name, None)


def is_task_form_allowed(name):
    """Whether a flow may name the task form ``name``: registered with
    :func:`register_task_form`, or a dotted path the flow allowlist permits."""
    return isinstance(name, str) and bool(name) and (
        name in _registry or is_allowed(name))


def get_task_form(name):
    """The form class of ``name``: the one registered under it, or the class
    at that dotted path when the flow allowlist permits it.
    ImproperlyConfigured otherwise.

    A form class is returned as it is (Python flows pass the class).
    """
    if isinstance(name, type) and issubclass(name, forms.BaseForm):
        return name
    if isinstance(name, str) and name in _registry:
        return _registry[name]
    if is_task_form_allowed(name):
        try:
            form_class = import_string(name)
        except ImportError as error:
            raise ImproperlyConfigured('Task form %r: %s' % (name, error)) from None
        if isinstance(form_class, type) and issubclass(form_class, forms.BaseForm):
            return form_class
        raise ImproperlyConfigured('%r is not a form class' % (name,))
    raise ImproperlyConfigured('No task form named %r: register it with '
                               'register_task_form() or allow its path in '
                               'GT_FLOWS_ALLOWED_CALLABLES' % (name,))


class BlockedTaskForm:
    """The form of a ``human_task`` of a stored JSON flow that names a form
    which is not allowed. The flow still loads; :meth:`resolve` is asked when
    the flow reaches the activity, and refuses (logged) while the name is not
    allowed. Allowing or registering it later needs no new version."""

    def __init__(self, name, where):
        self.name = name
        self.where = where

    def resolve(self):
        """The form class, now that it is allowed; :class:`~djgentelella.
        flows.callables.CallableNotAllowed`, logged, while it is not."""
        if not is_task_form_allowed(self.name):
            raise CallableNotAllowed(_refuse(self.name, self.where))
        return get_task_form(self.name)

    def __str__(self):
        return self.name


def validate_task_forms(document):
    """``"<path>: <problem>"`` for each ``human_task`` of a JSON ``document``
    whose ``form`` is not allowed, or is not a form class."""
    errors = []
    states = document.get('states') if isinstance(document, dict) else None
    for index, state in enumerate(states if isinstance(states, list) else ()):
        if not isinstance(state, dict) or state.get('type') != 'human_task' \
                or not state.get('form'):
            continue
        where = '$.states[%d].form' % index
        name = state['form']
        if not is_task_form_allowed(name):
            errors.append('%s: %s is not an allowed task form (register it with '
                          'register_task_form or list it in '
                          'GT_FLOWS_ALLOWED_CALLABLES)' % (where, name))
            continue
        try:
            get_task_form(name)
        except ImproperlyConfigured as error:
            errors.append('%s: %s' % (where, error))
    return errors


def task_form_name(form):
    """The name a form (a name or a registered class) is known by."""
    if isinstance(form, str):
        return form
    for name, form_class in _registry.items():
        if form_class is form:
            return name
    return form_path(form)


def get_task_forms():
    """``{name: form class}`` of every registered task form."""
    return dict(_registry)
