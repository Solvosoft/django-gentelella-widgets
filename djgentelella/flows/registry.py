"""What the engine knows, as plain JSON: the flows declared in Python, the
registered conditions, actions and task forms, the keys each activity
type takes and the types of flow variables.

It is the public face of the registries for tools built on top of the
engine -- a flow designer builds its catalogue from :func:`catalogue` -- so
none of them has to read a private ``_registry``. Every function returns
lists and dicts of strings, numbers and booleans (``json.dumps`` takes them
as they are), sorted by name. Only :func:`registered_flows` with
``published=True`` reads the database.
"""

from djgentelella.flows import base, conditions, taskforms, variables
from djgentelella.flows.actions import get_actions
from djgentelella.flows.definitions import ARGUMENTS, COMMON
from djgentelella.flows.models import FlowDefinition
from djgentelella.flows.schema import CURRENT

__all__ = ['ARGUMENTS', 'COMMON', 'activity_arguments', 'catalogue',
           'registered_actions', 'registered_conditions', 'registered_flows',
           'registered_task_forms', 'variable_types']


def summary(obj):
    """The first paragraph of ``obj``'s docstring, on one line."""
    text = (getattr(obj, '__doc__', None) or '').strip().split('\n\n')[0]
    return ' '.join(text.split())


def registered_actions():
    """``[{"name", "class", "help", "props_schema", "on_commit"}]``: the
    actions :func:`~djgentelella.flows.actions.action_from_json` can build;
    ``props_schema`` is the JSON Schema of their props."""
    return [{'name': name, 'class': '%s.%s' % (cls.__module__, cls.__qualname__),
             'help': summary(cls), 'props_schema': cls.props_schema,
             'on_commit': bool(getattr(cls, 'on_commit', False))}
            for name, cls in sorted(get_actions().items())]


def registered_conditions():
    """``[{"name", "help"}]``: the conditions registered with
    :func:`~djgentelella.flows.conditions.register_condition`, which a JSON
    flow names as ``"<name>"`` or ``{"function": "<name>"}``."""
    return [{'name': name, 'help': summary(function)}
            for name, function in sorted(conditions.get_conditions().items())]


def _flow_entry(flow, source, versions):
    return {'name': flow.name, 'title': str(flow.title or ''),
            'model': flow.model._meta.label, 'source': source,
            'versions': sorted(versions), 'initial': flow.initial,
            'states': [{'id': key, 'label': str(activity.label),
                        'type': activity.type}
                       for key, activity in flow.activities.items()],
            'transitions': [transition.name for transition in flow.transitions],
            'auto': {transition.name: bool(transition.auto)
                     for transition in flow.transitions}}


def registered_flows(published=False, site=None):
    """``[{"name", "title", "model", "source", "versions", "initial",
    "states", "transitions", "auto"}]`` of the flows declared in Python
    (``source="python"``), each described by its newest version.
    ``transitions`` are the names of its transitions and ``auto`` says,
    by name, which of them run by themselves (``auto=True``): no user can
    run those.

    With ``published``, also the active ``FlowDefinition``\\ s of ``site`` (or
    global) as ``source="definition"`` -- this reads the database; a name
    published that way replaces the Python one, as :func:`get_flow` does.
    """
    found = {}
    for name, versions in base.registered_flow_classes().items():
        flow = versions[max(versions)]
        found[name] = _flow_entry(flow, 'python', versions)
    if published:
        names = FlowDefinition.objects.filter(is_active=True).values_list(
            'name', flat=True).distinct()
        for name in sorted(set(names)):
            flow = base.get_flow(name, site=site)
            if flow is None or flow.definition is None:
                continue
            versions = FlowDefinition.objects.filter(name=name).values_list(
                'version', flat=True)
            found[name] = _flow_entry(flow, 'definition', set(versions))
    return [found[name] for name in sorted(found)]


def registered_task_forms():
    """``[{"name", "class", "fields"}]`` of the forms registered with
    :func:`~djgentelella.flows.taskforms.register_task_form`; each field is
    ``{"name", "label", "required", "type"}``."""
    result = []
    for name, form_class in sorted(taskforms.get_task_forms().items()):
        result.append({
            'name': name, 'class': taskforms.form_path(form_class),
            'fields': [{'name': field_name, 'label': str(field.label or ''),
                        'required': bool(field.required),
                        'type': type(field).__name__}
                       for field_name, field in form_class.base_fields.items()]})
    return result


def activity_arguments():
    """``{"common": [...], "types": {type: [...]}}``: the keys every activity
    of a JSON flow takes (:data:`COMMON`) and those of each type
    (:data:`ARGUMENTS`)."""
    return {'common': list(COMMON),
            'types': {kind: list(keys) for kind, keys in sorted(ARGUMENTS.items())}}


def variable_types():
    """``[{"name", "label", "json_types"}]``: the types a flow variable can
    be declared with (:mod:`djgentelella.flows.variables`), sorted by name
    (:func:`~djgentelella.flows.variables.get_variable_types` keeps the order
    of registration)."""
    return [found.describe()
            for _name, found in sorted(variables.get_variable_types().items())]


def catalogue(published=False, site=None):
    """The registries above in one document: ``schema_version``,
    ``activities`` (:func:`activity_arguments`), ``actions``, ``conditions``,
    ``task_forms`` and ``flows``. :func:`variable_types` is asked apart."""
    return {'schema_version': CURRENT, 'activities': activity_arguments(),
            'actions': registered_actions(),
            'conditions': registered_conditions(),
            'task_forms': registered_task_forms(),
            'flows': registered_flows(published=published, site=site)}
