"""Flows: an object goes through activities -- states with transitions,
switches, waits, parallel branches, subflows, human tasks and automatic
actions. See :mod:`djgentelella.flows.base` and ``docs/source/flows.rst``.

``djgentelella.flows`` is a Django app (label ``gtflows``): add it to
``INSTALLED_APPS``. This package is imported while the app registry is still
loading, so it imports nothing at first; the names below are fetched from
their modules the first time they are used (``from djgentelella.flows import
Flow`` works once the apps are ready). Never import it from a ``models.py``
other than its own.
"""

from importlib import import_module

_EXPORTS = {
    'djgentelella.flows.actions': [
        'Action', 'ActionContext', 'Assign', 'CallFunction', 'CreateTask', 'Notify',
        'SendEmail', 'SetField', 'SetVariable', 'StartFlow', 'action_from_json',
        'get_action', 'get_actions', 'register_action',
    ],
    'djgentelella.flows.activities': [
        'ActionActivity', 'Activity', 'HumanTask', 'Join', 'Parallel', 'State',
        'Subflow', 'Switch', 'Wait',
    ],
    'djgentelella.flows.base': [
        'ANY_STATE', 'Deadline', 'Flow', 'Transition', 'flow_for_instance',
        'get_flow', 'get_flows', 'register_flow',
    ],
    'djgentelella.flows.conditions': ['register_condition'],
    'djgentelella.flows.definitions': [
        'build_flow', 'export_definition', 'export_definitions', 'import_definition',
        'publish_definition', 'validate_definition_data',
    ],
    'djgentelella.flows.exceptions': [
        'ActionNotAllowed', 'TaskNotAllowed', 'TransitionBlocked',
        'TransitionNotAllowed',
    ],
    'djgentelella.flows.signals': [
        'action_blocked', 'flow_state_changed', 'post_transition', 'pre_transition',
        'task_completed', 'task_created',
    ],
    'djgentelella.flows.tasks': ['create_task'],
    'djgentelella.flows.callables': [
        'DocumentError', 'register_callable', 'validate_actions',
        'validate_callables',
    ],
    'djgentelella.flows.registry': [
        'ARGUMENTS', 'COMMON', 'activity_arguments', 'catalogue',
        'registered_actions', 'registered_conditions', 'registered_flows',
        'registered_task_forms', 'variable_types',
    ],
    'djgentelella.flows.taskforms': [
        'get_task_form', 'is_task_form_allowed', 'register_task_form',
        'validate_task_forms',
    ],
    'djgentelella.flows.models': ['forget_object'],
    'djgentelella.flows.variables': [
        'check_variable', 'get_variable_type', 'register_variable_type',
    ],
}
_WHERE = {name: module for module, names in _EXPORTS.items() for name in names}

__all__ = sorted(_WHERE)


def __getattr__(name):
    module = _WHERE.get(name)
    if module is None:
        raise AttributeError('module %r has no attribute %r' % (__name__, name))
    value = getattr(import_module(module), name)
    globals()[name] = value
    return value


def __dir__():
    return __all__
