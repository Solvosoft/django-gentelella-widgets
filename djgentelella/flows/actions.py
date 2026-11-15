"""What a flow does besides moving: set a field, assign, notify, email, call a
function, create a task, start another flow...

Each action is an object with ``run(context)``, where ``context`` is an
:class:`ActionContext`. They run in order, inside the transaction of the
change: one that raises undoes the whole transition (or, in an ``action``
activity, leaves the instance in error, to ``retry`` later).

An action whose ``on_commit`` is true runs only after that transaction
commits instead -- the place for anything a rollback cannot undo (an HTTP
call, a message queue, a file). Write custom actions that leave the database
that way, or call ``context.on_commit(...)`` from ``run``.

**Registry.** Every action class has a ``name`` and a ``props_schema`` (JSON
Schema): :func:`action_from_json` builds one from ``{"action": "<name>",
"props": {...}}``, which is how JSON flow definitions and automations declare
them. The props are the keyword arguments of the class. Register your own
with :func:`register_action`.

Recipients (``to``, ``owners``) are ``'actor'`` (who runs the transition),
``'assigned'`` (the instance's user, or the members of its group),
``'field:<path>'`` (an attribute of the object, following foreign keys),
``'variable:<name>'`` (a user pk or username kept in the variables),
``'user:<username>'``, ``'group:<name>'`` (its members), a callable
``(context) -> value``, or -- for emails -- a literal address or
async_notification identifier such as ``'editors@group.local'``.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import Manager, QuerySet
from django.template import Context, Template
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _

from djgentelella.flows import signals
from djgentelella.flows.callables import guard_action
from djgentelella.flows.exceptions import ActionNotAllowed, TransitionNotAllowed
from djgentelella.flows.schema import validate
from djgentelella.flows.tasks import create_task
from djgentelella.flows.utils import json_safe, to_timedelta, value_at
from djgentelella.notification import create_notification
from djgentelella.sites import get_current_site

logger = logging.getLogger(__name__)

_registry = {}


class ActionContext:
    """What an action (or a condition) sees while it runs.

    Inside a flow, ``flow`` and ``instance`` are set and ``variables`` is the
    instance's own dict: what an action writes there is saved with it.
    Automations run actions with ``flow=None`` and ``instance=None``.
    ``user`` is ``None`` for the system.
    """

    def __init__(self, obj=None, user=None, data=None, variables=None, site=None,
                 request=None, flow=None, instance=None, transition=None,
                 activity=None, task=None, policy=None, render_context=None):
        self.obj = obj
        self.user = user
        self.data = data if data is not None else {}
        if variables is None:
            variables = instance.variables if instance is not None else {}
        self.variables = variables
        if site is None and instance is not None:
            site = instance.site
        if site is None and request is not None:
            site = get_current_site(request)
        self.site = site
        self.request = request
        self.flow = flow
        self.instance = instance
        self.transition = transition
        self.activity = activity
        self.task = task
        #: ``allowed(action, context) -> bool`` (an object with that method,
        #: or a callable) asked before each action runs, on top of
        #: ``GT_FLOWS_ACTION_POLICY``. See :func:`check_action`.
        self.policy = policy
        #: ``(context) -> dict``: the context the texts of the actions are
        #: rendered with, instead of :attr:`template_context`.
        self.render_context_hook = render_context

    @property
    def template_context(self):
        """Everything an action's text could use: the object, the user, the
        flow, the transition, the activity, the data, the variables, the
        instance and the task."""
        return {'object': self.obj, 'user': self.user, 'flow': self.flow,
                'transition': self.transition, 'activity': self.activity,
                'data': self.data, 'variables': self.variables,
                'instance': self.instance, 'task': self.task}

    def render_context(self):
        """The context the texts of the actions (messages, titles, email
        templates, ``{{ }}`` values) are rendered with: what the
        ``render_context`` hook returns, or :attr:`template_context`.

        The hook is how a caller that runs actions for someone it does not
        trust -- an automation of an ordinary user -- reduces what those
        texts can reach.
        """
        if self.render_context_hook is not None:
            return dict(self.render_context_hook(self))
        return self.template_context

    def on_commit(self, function):
        """Run ``function()`` once the current transaction commits.

        For anything outside the database -- an HTTP call, a message queue,
        a file -- which a rollback could not undo.
        """
        transaction.on_commit(function)


def _as_policy(policy):
    if policy is None:
        return None
    if isinstance(policy, str):
        policy = import_string(policy) if policy else None
    if policy is not None and not callable(policy) and hasattr(policy, 'allowed'):
        return policy.allowed
    return policy


def action_policies(context=None):
    """The policies asked before an action runs in ``context``:
    ``GT_FLOWS_ACTION_POLICY`` (a callable, an object with ``allowed``, or
    the dotted path of one) and the context's own ``policy``."""
    found = [_as_policy(getattr(settings, 'GT_FLOWS_ACTION_POLICY', None)),
             _as_policy(getattr(context, 'policy', None))]
    return [policy for policy in found if policy is not None]


def action_allowed(action, context):
    """``(allowed, reason)``: whether every policy lets ``action`` run in
    ``context``. A policy that raises refuses (it fails closed): an
    ``ActionNotAllowed`` it raises keeps its message as the reason; any other
    error is logged with its detail and the reason is the generic one, so
    nothing internal reaches the user."""
    refused = _('The action %(action)s is not allowed here.') % {
        'action': getattr(action, 'name', '') or type(action).__name__}
    for policy in action_policies(context):
        try:
            if not policy(action, context):
                return False, refused
        except ActionNotAllowed as error:
            return False, str(error) or refused
        except Exception:
            logger.exception('The action policy %r failed on %r', policy, action)
            return False, refused
    return True, ''


def check_action(action, context):
    """Raise :class:`~djgentelella.flows.exceptions.ActionNotAllowed` -- after
    logging it and sending ``action_blocked`` -- when a policy refuses
    ``action``. :func:`run_actions` calls it before each action."""
    allowed, reason = action_allowed(action, context)
    if allowed:
        return
    obj = getattr(context, 'obj', None)
    logger.warning('Action %s blocked by the action policy (object %r, user %r, '
                   'flow %r): %s', getattr(action, 'name', type(action).__name__),
                   obj, getattr(context, 'user', None),
                   getattr(getattr(context, 'flow', None), 'name', None), reason)
    signals.action_blocked.send(sender=type(action), action=action,
                                context=context, reason=reason)
    raise ActionNotAllowed(reason)


def run_actions(actions, context):
    """Run ``actions`` in order; the ``on_commit`` ones after the commit.

    Each action is checked by the action policy first (:func:`check_action`):
    a refused one stops the run with ``ActionNotAllowed``.
    """
    for action in actions:
        check_action(action, context)
        if getattr(action, 'on_commit', False):
            context.on_commit(lambda action=action: action.run(context))
        else:
            action.run(context)


# -- recipients ------------------------------------------------------------------
def _user(value):
    User = get_user_model()
    if value is None or isinstance(value, User):
        return value
    if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
        return User.objects.filter(pk=value).first()
    return User.objects.filter(username=value).first()


def resolve(target, context):
    """A list of users or strings for one recipient specification."""
    if callable(target):
        found = target(context)
    elif target == 'actor':
        found = context.user
    elif target == 'assigned':
        instance = context.instance
        if instance is None:
            found = None
        elif instance.assigned_to_id:
            found = instance.assigned_to
        elif instance.assigned_group_id:
            found = list(instance.assigned_group.user_set.all())
        else:
            found = None
    elif isinstance(target, str) and target.startswith('field:'):
        found = value_at(context.obj, target[len('field:'):])
    elif isinstance(target, str) and target.startswith('variable:'):
        value = value_at(context.variables, target[len('variable:'):])
        found = [_user(item) for item in value] if isinstance(value, list) \
            else _user(value)
    elif isinstance(target, str) and target.startswith('user:'):
        found = _user(target[len('user:'):])
    elif isinstance(target, str) and target.startswith('group:'):
        found = list(get_user_model().objects.filter(
            groups__name=target[len('group:'):], is_active=True))
    else:
        found = target
    if found is None:
        return []
    if isinstance(found, Manager):  # field:<m2m> or a reverse relation
        found = found.all()
    found = list(found) if isinstance(found, (list, tuple, set, QuerySet)) else [found]
    return [item for item in found if item is not None]


def recipients(spec, context):
    specs = spec if isinstance(spec, (list, tuple)) else [spec]
    return [found for item in specs for found in resolve(item, context)]


def users(spec, context):
    """Only the users among the recipients of ``spec``, each once."""
    User = get_user_model()
    found = {}
    for item in recipients(spec, context):
        if isinstance(item, User):
            found.setdefault(item.pk, item)
    return list(found.values())


def render_context(context):
    """``context.render_context()``, or its ``template_context`` for a
    context object that predates the hook."""
    method = getattr(context, 'render_context', None)
    return method() if callable(method) else context.template_context


def render(text, context):
    """``text`` as a template, with the context's render context."""
    return Template(text).render(Context(render_context(context)))


def detail_url(context):
    if context.flow is None or context.obj is None:
        return '#'
    try:
        return reverse('flow_detail', args=[context.flow.name, context.obj.pk])
    except NoReverseMatch:
        return '#'


# -- the registry ----------------------------------------------------------------
def register_action(cls):
    """Register an :class:`Action` subclass under its ``name`` (also usable
    as a class decorator); a name registered again is replaced."""
    if not getattr(cls, 'name', ''):
        raise ImproperlyConfigured('%s has no name' % cls.__name__)
    _registry[cls.name] = cls
    return cls


def get_action(name):
    try:
        return _registry[name]
    except KeyError:
        raise ImproperlyConfigured('No flow action named %r' % name) from None


def get_actions():
    return dict(_registry)


def action_from_json(spec, where='call action'):
    """``{"action": "send_email", "props": {...}}`` as an action object.

    The props are checked against the class's ``props_schema`` first. A JSON
    action is data, so the ``function`` of a ``call`` goes through the
    allowlist of :mod:`djgentelella.flows.callables` when it runs, whoever
    builds it (``where`` names it in the log of a refusal).
    """
    if not isinstance(spec, dict) or 'action' not in spec:
        raise ImproperlyConfigured('An action is {"action": name, "props": {...}}, '
                                   'not %r' % (spec,))
    cls = get_action(spec['action'])
    props = spec.get('props') or {}
    errors = validate(props, cls.props_schema, '$.%s' % cls.name)
    if errors:
        raise ImproperlyConfigured('; '.join(errors))
    return guard_action(cls(**props), where)


#: A recipient specification, or a list of them.
RECIPIENTS = {'type': ['string', 'array'], 'items': {'type': 'string'}}


class Action:
    #: The registry key, the ``"action"`` of the JSON form.
    name = ''
    #: JSON Schema of the props (the keyword arguments of ``__init__``).
    props_schema = {'type': 'object'}
    #: Run after the transaction commits, not inside it.
    on_commit = False
    #: Sets the instance's assignment (so the transition does not clear it).
    assigns = False

    def run(self, context):
        raise NotImplementedError


@register_action
class SetField(Action):
    """``obj.<field> = value`` and save it. ``value`` may be a callable that
    gets the context; ``variable`` takes it from the variables instead."""

    name = 'set_field'
    props_schema = {'type': 'object', 'required': ['field'],
                    'additionalProperties': False,
                    'properties': {'field': {'type': 'string', 'minLength': 1},
                                   'value': {}, 'variable': {'type': 'string'}}}

    def __init__(self, field, value=None, variable=None):
        self.field = field
        self.value = value
        self.variable = variable

    def run(self, context):
        if self.variable:
            value = value_at(context.variables, self.variable)
        else:
            value = self.value(context) if callable(self.value) else self.value
        setattr(context.obj, self.field, value)
        context.obj.save(update_fields=[self.field])


@register_action
class SetVariable(Action):
    """Set instance variables: ``SetVariable('total', 10)`` or
    ``SetVariable(values={'a': 1})``. A callable value gets the context; a
    string with ``{{`` is rendered as a template."""

    name = 'set_variable'
    props_schema = {'type': 'object', 'additionalProperties': False,
                    'properties': {'name': {'type': 'string', 'minLength': 1},
                                   'value': {}, 'values': {'type': 'object'}}}

    def __init__(self, name=None, value=None, values=None):
        self.values = dict(values or {})
        if name:
            self.values[name] = value

    def run(self, context):
        for key, value in self.values.items():
            if callable(value):
                value = value(context)
            elif isinstance(value, str) and '{{' in value:
                value = render(value, context)
            context.variables[key] = json_safe(value)


@register_action
class Assign(Action):
    """Assign the instance to a user and/or a group.

    ``user`` is a recipient (``'actor'``, ``'field:approver'``...), ``None``
    (clear) or a callable; ``group`` a group name, ``None`` or a callable. An
    assignment shows the object in that user's (or group's) flow inbox.
    """

    name = 'assign'
    props_schema = {'type': 'object', 'additionalProperties': False,
                    'properties': {'user': {'type': ['string', 'null']},
                                   'group': {'type': ['string', 'null']}}}
    assigns = True

    def __init__(self, user=None, group=None):
        self.user = user
        self.group = group

    def run(self, context):
        if context.instance is None:
            return
        user = None
        if self.user is not None:
            found = users(self.user, context)
            user = found[0] if found else None
        group = self.group(context) if callable(self.group) else self.group
        if isinstance(group, str):
            try:
                group = Group.objects.get(name=group)
            except Group.DoesNotExist:
                raise TransitionNotAllowed(
                    'The group %r this transition assigns to does not exist.'
                    % group) from None
        context.instance.assigned_to = user
        context.instance.assigned_group = group


@register_action
class Notify(Action):
    """An in-app notification (``djgentelella.notification``) to users."""

    name = 'notify'
    props_schema = {'type': 'object', 'required': ['message'],
                    'additionalProperties': False,
                    'properties': {'message': {'type': 'string', 'minLength': 1},
                                   'to': RECIPIENTS,
                                   'message_type': {'enum': ['info', 'success',
                                                             'warning', 'danger',
                                                             'default']}}}

    def __init__(self, message, to='actor', message_type='info'):
        self.message = message
        self.to = to
        self.message_type = message_type

    def run(self, context):
        message = render(self.message, context)
        for user in users(self.to, context):
            create_notification(message, user, self.message_type,
                                link=detail_url(context))


@register_action
class SendEmail(Action):
    """An email from an async_notification ``EmailTemplate`` (by ``code``)."""

    name = 'send_email'
    props_schema = {'type': 'object', 'required': ['code', 'to'],
                    'additionalProperties': False,
                    'properties': {'code': {'type': 'string', 'minLength': 1},
                                   'to': RECIPIENTS}}

    def __init__(self, code, to):
        self.code = code
        self.to = to

    def run(self, context):
        # async_notification is an optional app: only flows that email need it.
        from djgentelella.async_notification.sending import (  # noqa: PLC0415
            send_email_from_template,
        )
        addresses = [getattr(found, 'email', found)
                     for found in recipients(self.to, context)]
        addresses = [address for address in addresses if address]
        if addresses:
            send_email_from_template(self.code, addresses,
                                     render_context(context), user=context.user)


@register_action
class CallFunction(Action):
    """Call ``function(context)``; ``function`` may be a dotted path.

    A path given in Python is code and is imported as is; built from JSON
    (:func:`action_from_json`) it has to be allowed."""

    name = 'call'
    props_schema = {'type': 'object', 'required': ['function'],
                    'additionalProperties': False,
                    'properties': {'function': {'type': 'string', 'minLength': 1},
                                   'on_commit': {'type': 'boolean'}}}

    def __init__(self, function, on_commit=False):
        self.function = function
        self.on_commit = on_commit

    def run(self, context):
        function = self.function
        if isinstance(function, str):
            function = import_string(function)
        function(context)


@register_action
class CreateTask(Action):
    """A task on the object that nothing waits for (an ``instance``-less one,
    see :func:`~djgentelella.flows.tasks.create_task`). To make the flow wait
    for its outcome, use a ``human_task`` activity instead."""

    name = 'create_task'
    props_schema = {
        'type': 'object', 'required': ['title'], 'additionalProperties': False,
        'properties': {'title': {'type': 'string', 'minLength': 1},
                       'description': {'type': 'string'},
                       'owners': RECIPIENTS,
                       'groups': {'type': 'array', 'items': {'type': 'string'}},
                       'priority': {'type': 'integer', 'minimum': 1, 'maximum': 5},
                       'due': {'type': ['string', 'integer']},
                       'outcome_choices': {'type': 'array',
                                           'items': {'type': 'string'}},
                       'data': {'type': 'object'}}}

    def __init__(self, title, description='', owners=(), groups=(), priority=3,
                 due=None, outcome_choices=('approve', 'reject'), data=None):
        self.title = title
        self.description = description
        self.owners = owners
        self.groups = groups
        self.priority = priority
        self.due = due
        self.outcome_choices = outcome_choices
        self.data = data

    def run(self, context):
        due = to_timedelta(self.due)
        create_task(obj=context.obj, title=render(self.title, context),
                    description=render(self.description, context),
                    potential_owners=users(self.owners, context) if self.owners else (),
                    groups=self.groups, priority=self.priority,
                    due=timezone.now() + due if due else None,
                    outcome_choices=self.outcome_choices, data=self.data,
                    user=context.user)


@register_action
class StartFlow(Action):
    """Start flow ``flow`` on the object (or on ``obj``: a ``'field:<path>'``
    or a callable), with ``variables``. It runs on its own: nothing waits for
    it -- that is what a ``subflow`` activity is for."""

    name = 'start_flow'
    props_schema = {'type': 'object', 'required': ['flow'],
                    'additionalProperties': False,
                    'properties': {'flow': {'type': 'string', 'minLength': 1},
                                   'obj': {'type': 'string'},
                                   'variables': {'type': 'object'}}}

    def __init__(self, flow, obj=None, variables=None):
        self.flow = flow
        self.obj = obj
        self.variables = variables

    def run(self, context):
        from djgentelella.flows.base import get_flow  # noqa: PLC0415 (circular)
        flow = get_flow(self.flow, site=context.site)
        if flow is None:
            raise ImproperlyConfigured('start_flow: no flow named %r' % self.flow)
        obj = context.obj
        if self.obj is not None:
            found = resolve(self.obj, context)
            obj = found[0] if found else None
        if obj is None:
            raise ImproperlyConfigured('start_flow: no object to start %r on'
                                       % self.flow)
        variables = self.variables(context) if callable(self.variables) \
            else dict(self.variables or {})
        flow.start(obj, context.user, variables=variables, request=context.request)
