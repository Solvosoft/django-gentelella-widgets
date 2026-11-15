"""Flows written as JSON: the format of ``schema_v2.json``, loaded at runtime.

:func:`build_flow` turns a document into the same
:class:`~djgentelella.flows.base.Flow` a Python class declares, so the engine,
the pages and the diagram do not tell them apart. Python callables have a
JSON spelling each:

* a condition is the name of a function registered with
  :func:`~djgentelella.flows.conditions.register_condition` (or a dotted
  path), ``{"function": name}``, or a condition of
  :mod:`djgentelella.authorization` (checked by :func:`validate_conditions`
  when publishing);
* an action is ``{"action": "<name>", "props": {...}}``
  (:func:`~djgentelella.flows.actions.action_from_json`);
* a transition's form is the dotted path of its class; a ``human_task``'s,
  the name of a form registered with
  :func:`~djgentelella.flows.taskforms.register_task_form` or the dotted path
  of its class. Both paths have to be allowed
  (:mod:`djgentelella.flows.callables`);
* a duration is seconds or ISO 8601 (``"P2D"``, ``"PT4H"``).

:func:`publish_definition` stores a document as a new version of a
:class:`~djgentelella.flows.models.FlowDefinition`; ``manage.py
gtflows_publish <file.json>`` does it from a file.
"""

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import Max
from django.utils.module_loading import import_string

from djgentelella.flows.actions import action_from_json
from djgentelella.flows.activities import TYPES
from djgentelella.flows.base import Deadline, Flow, Transition
from djgentelella.flows.callables import (
    blocked_form,
    guard_action,
    guard_condition,
    is_allowed,
    validate_callables,
)
from djgentelella.flows.conditions import check_condition
from djgentelella.flows.models import FlowDefinition
from djgentelella.flows.schema import CURRENT, validate_document
from djgentelella.flows.taskforms import (
    BlockedTaskForm,
    is_task_form_allowed,
    validate_task_forms,
)
from djgentelella.flows.utils import to_timedelta

#: The keys of an activity that are not arguments of its class.
COMMON = ('id', 'type', 'label', 'help_text', 'on_enter', 'on_exit')
#: Which keys each type takes, besides the common ones.
ARGUMENTS = {
    'state': ('deadline',),
    'switch': ('cases', 'default'),
    'action': ('actions', 'next'),
    'wait': ('after', 'until', 'signal', 'next'),
    'parallel': ('branches',),
    'join': ('wait_for', 'next'),
    'subflow': ('flow', 'obj', 'variables', 'next', 'outcomes'),
    'human_task': ('title', 'description', 'owners', 'groups', 'outcomes', 'next',
                   'priority', 'due', 'on_expire', 'each', 'min', 'form'),
}


def actions(specs):
    return [guard_action(action_from_json(spec), 'call action')
            for spec in specs or ()]


def guarded_cases(cases, activity_id):
    """The cases of a ``switch``, with the callables they name checked when
    they run (:mod:`djgentelella.flows.callables`)."""
    return [dict(case, condition=guard_condition(
        case['condition'], 'case of %s' % activity_id))
        if isinstance(case, dict) and 'condition' in case else case
        for case in cases or ()]


def deadline(spec):
    return Deadline(to_timedelta(spec['after']), transition=spec.get('transition'),
                    actions=actions(spec.get('actions')))


def activity(spec):
    kind = spec.get('type', 'state')
    extra = sorted(set(spec) - set(COMMON) - set(ARGUMENTS[kind]))
    if extra:
        raise ImproperlyConfigured('Activity %r (%s) does not take %s' % (
            spec['id'], kind, ', '.join(extra)))
    kwargs = {key: spec[key] for key in ARGUMENTS[kind] if key in spec}
    if kind == 'state' and 'deadline' in kwargs:
        kwargs['deadline'] = deadline(kwargs['deadline'])
    if kind == 'action':
        kwargs['actions'] = actions(kwargs.get('actions'))
    if kind == 'switch':
        kwargs['cases'] = guarded_cases(kwargs.get('cases'), spec['id'])
    if kind == 'human_task' and kwargs.get('form') and \
            not is_task_form_allowed(kwargs['form']):
        kwargs['form'] = BlockedTaskForm(kwargs['form'], 'form of %s' % spec['id'])
    return TYPES[kind](spec['id'], spec.get('label'), on_enter=actions(
        spec.get('on_enter')), on_exit=actions(spec.get('on_exit')),
        help_text=spec.get('help_text', ''), **kwargs)


def transition(spec):
    kwargs = {key: value for key, value in spec.items()
              if key not in ('name', 'source', 'target', 'actions', 'form')}
    if 'condition' in kwargs:
        kwargs['condition'] = guard_condition(
            kwargs['condition'], 'condition of %s' % spec['name'])
    form = transition_form(spec, kwargs)
    return Transition(spec['name'], spec['source'], spec['target'], form=form,
                      actions=actions(spec.get('actions')), **kwargs)


def transition_form(spec, kwargs):
    """The form class of a transition; one that is not allowed blocks the
    transition instead (:mod:`djgentelella.flows.callables`)."""
    path = spec.get('form')
    if not path:
        return None
    if not is_allowed(path):
        kwargs['condition'] = blocked_form(path, 'form of %s' % spec['name'])
        return None
    return import_string(path)


def build_flow(document, definition=None):
    """The :class:`Flow` of a JSON ``document``; ImproperlyConfigured, with
    every problem found, when it is not valid."""
    errors = validate_document(document)
    if errors:
        raise ImproperlyConfigured('Invalid flow definition: ' + '; '.join(errors))
    try:
        model = apps.get_model(document['model'])
    except (LookupError, ValueError):
        raise ImproperlyConfigured('Unknown model %r' % document['model']) from None
    attributes = {
        'name': document['name'], 'title': document.get('title', ''),
        'model': model, 'initial': document['initial'],
        'states': [activity(spec) for spec in document['states']],
        'transitions': [transition(spec) for spec in document.get('transitions', ())],
        'final_states': document.get('final_states'),
        'variables': document.get('variables', {}),
        'on_enter': {state: actions(specs)
                     for state, specs in document.get('on_enter', {}).items()},
        'on_exit': {state: actions(specs)
                    for state, specs in document.get('on_exit', {}).items()},
        'deadlines': {state: deadline(spec)
                      for state, spec in document.get('deadlines', {}).items()},
        'definition': definition,
        'version': definition.version if definition is not None
        else document.get('version', 1),
    }
    for key in ('max_auto_steps', 'reassign_perms', 'control_perms'):
        if key in document:
            attributes[key] = document[key]
    return Flow(**attributes)


def validate_conditions(document):
    """The problems of the authorization conditions of ``document``: those of
    the transitions and of the ``switch`` cases, unknown authorizations
    included.

    :func:`build_flow` does not check the names, so a stored flow still loads
    after an authorization goes away (it is then ``False``); publishing does.
    """
    errors = []
    for index, spec in enumerate(document.get('transitions') or ()):
        if isinstance(spec, dict) and 'condition' in spec:
            errors += check_condition(spec['condition'],
                                      '$.transitions[%d].condition' % index)
    for index, state in enumerate(document.get('states') or ()):
        cases = state.get('cases') if isinstance(state, dict) else None
        for number, case in enumerate(cases or ()):
            if isinstance(case, dict) and 'condition' in case:
                errors += check_condition(
                    case['condition'],
                    '$.states[%d].cases[%d].condition' % (index, number))
    return errors


def publish_definition(document, site=None, activate=True, version=None):
    """Store ``document`` as a new FlowDefinition and return it.

    It is checked first by building it. The version is ``version``, the
    document's own, or the next one of that name and site. With
    ``activate``, the older versions stop starting instances (they go on
    running the ones they have).
    """
    document = dict(document)
    document.setdefault('schema_version', CURRENT)
    build_flow(document)
    errors = (validate_conditions(document) + validate_callables(document)
              + validate_task_forms(document))
    if errors:
        raise ImproperlyConfigured('Invalid flow definition: ' + '; '.join(errors))
    name = document['name']
    with transaction.atomic():
        same = FlowDefinition.objects.filter(name=name, site=site)
        # PostgreSQL refuses FOR UPDATE with an aggregate: lock, then count.
        list(same.select_for_update().values_list('pk', flat=True))
        version = version or document.get('version') or (
            (same.aggregate(last=Max('version'))['last'] or 0) + 1)
        document['version'] = version
        definition = FlowDefinition.objects.create(
            name=name, version=version, site=site, title=document.get('title', ''),
            document=document, is_active=activate)
        if activate:
            same.exclude(pk=definition.pk).update(is_active=False)
    return definition
