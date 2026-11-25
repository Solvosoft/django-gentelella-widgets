"""The flow engine: activities, transitions and their actions over any model.

A flow is declared as a class and registered::

    class ReviewFlow(Flow):
        model = Article
        title = _('Article review')
        states = [('draft', _('Draft')), ('review', _('In review')),
                  ('published', _('Published'))]
        initial = 'draft'
        transitions = [
            Transition('submit', 'draft', 'review', label=_('Submit'),
                       perms=['news.change_article'],
                       actions=[Assign(group='Editors')]),
            Transition('publish', 'review', 'published', label=_('Publish'),
                       perms=['news.publish_article'],
                       condition=lambda context: context.obj.author != context.user,
                       actions=[Notify('{{ object }} is out.', to='field:author')]),
        ]

    register_flow(ReviewFlow)

usually in ``<app>/gtflows.py``, which djgentelella imports at startup -- or
written as JSON and loaded into a
:class:`~djgentelella.flows.models.FlowDefinition`
(:mod:`djgentelella.flows.definitions`). Both build the same :class:`Flow`.

``states`` may also hold the other kinds of activity of
:mod:`djgentelella.flows.activities`: switches, waits, parallel branches,
subflows, human tasks and automatic actions.

Where an object stands lives in
:class:`~djgentelella.flows.models.FlowInstance`, not on the model: an
object without one is in the ``initial`` state. The instance keeps its
``variables``, the *tokens* of the activities under way, a status
(running, suspended, error, completed, terminated) and the version of the
flow it started with.

**Authorization.** A transition runs only when the object is in one of its
source states, the user has *all* of its ``perms`` and its ``condition``
(if any) holds. Which objects a user may reach at all -- the inbox, the
detail and history pages -- is :meth:`Flow.get_queryset`: by default the
objects of the model if the user holds ``<app>.view_<model>``, otherwise only
the objects they can act on or are assigned to.

**The system.** Automatic transitions, activities and timers run with
``user=None``: no permission is checked for it, but the state and the
condition are, so a condition has to accept ``context.user is None``.
Code runs a transition as the system -- seeding data, a migration, a
command -- with ``Flow.run(obj, name, system=True)``: the flag is explicit,
so a ``user`` that happens to be ``None`` (or anonymous) is refused as
before instead of passing for the system. :meth:`Flow.start` checks no
permission: ``start(obj)`` without a user is a start by the system.

**Concurrency.** Every change locks the instance and reloads the object with
``select_for_update()``, so two users racing for one transition cannot both
win on databases that lock rows (PostgreSQL, MySQL). SQLite does not lock
rows: there, concurrent transitions are serialized only by its database lock.
"""

import copy
import logging
from collections import deque

from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections, models, router, transaction
from django.db.backends.signals import connection_created
from django.db.models import CharField, Exists, OuterRef, Q, Subquery, Value
from django.db.models.functions import Cast, Coalesce, Replace
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.forms import ModelForm
from django.forms.models import construct_instance
from django.utils import timezone
from django.utils.translation import gettext as _

from djgentelella.flows import signals
from djgentelella.flows.actions import ActionContext, run_actions
from djgentelella.flows.activities import FlowError, State, Subflow
from djgentelella.flows.conditions import evaluate
from djgentelella.flows.exceptions import (
    TaskNotAllowed,
    TransitionBlocked,
    TransitionNotAllowed,
)
from djgentelella.flows.models import (
    FlowDefinition,
    FlowInstance,
    FlowTransitionLog,
    Task,
    forget_object,
)
from djgentelella.flows.utils import json_safe, to_datetime
from djgentelella.sites import get_current_site, site_q

logger = logging.getLogger(__name__)

ANY_STATE = '*'
#: ``{name: {version: Flow}}`` of the flows declared in Python.
_registry = {}
#: Built JSON definitions: ``{(pk, updated_at): Flow}``.
_built = {}

RUNNING, SUSPENDED, ERROR = (FlowInstance.RUNNING, FlowInstance.SUSPENDED,
                             FlowInstance.ERROR)
COMPLETED, TERMINATED = FlowInstance.COMPLETED, FlowInstance.TERMINATED
#: Statuses in which an instance may still move.
LIVE = (RUNNING, ERROR)


class Deadline:
    """What happens when an object stays too long in a state.

    ``after`` is a ``timedelta`` from entering the state, or a callable
    ``(context) -> datetime``. When it passes, ``process_flow_timers`` runs
    ``actions`` (a reminder, an escalation) and then ``transition``, if any,
    as the system.
    """

    def __init__(self, after, transition=None, actions=None):
        self.after = after
        self.transition = transition
        self.actions = list(actions or [])

    def due(self, context):
        if callable(self.after):
            return self.after(context)
        return timezone.now() + self.after


class Transition:
    def __init__(self, name, source, target, label=None, form=None, perms=None,
                 condition=None, actions=None, icon='', css_class='btn-primary',
                 help_text='', keep_assignment=False, log_exclude=None, auto=False,
                 bulk=None, variables=False):
        self.name = name
        self.source = [source] if isinstance(source, str) else list(source)
        self.target = target
        self.label = label or name.replace('_', ' ').capitalize()
        self.form = form
        self.perms = list(perms or [])
        #: ``(context) -> bool``, a registered name or a condition dict; see
        #: :mod:`djgentelella.flows.conditions`.
        self.condition = condition
        self.actions = list(actions or [])
        self.icon = icon
        self.css_class = css_class
        self.help_text = help_text
        #: Keep the instance's assignment through this transition. By default
        #: a transition clears it, unless one of its actions assigns.
        self.keep_assignment = keep_assignment
        #: Form fields not to copy into the log (passwords, tokens...).
        self.log_exclude = set(log_exclude or ())
        #: Run by the engine, never by hand: right after the object enters a
        #: source state, when ``condition`` holds (always, without one).
        self.auto = auto
        #: Offered in the inbox for many objects at once; by default when it
        #: needs no form.
        self.bulk = bulk
        #: Copy the form's data into the instance variables: ``True`` for
        #: every field, or a list of field names.
        self.variables = variables

    @property
    def from_any_state(self):
        return ANY_STATE in self.source

    @property
    def bulkable(self):
        if self.auto:
            return False
        if self.bulk is not None:
            return self.bulk
        return self.form is None

    def __repr__(self):
        return '<Transition %s: %s -> %s>' % (self.name, self.source, self.target)


class Button:
    """A transition as the pages show it: runnable, or disabled with why."""

    def __init__(self, transition, disabled=False, reason=''):
        self.transition = transition
        self.disabled = disabled
        self.reason = reason

    def __getattr__(self, name):
        if name == 'transition':  # not set yet (copy, pickle)
            raise AttributeError(name)
        return getattr(self.transition, name)


class BulkResult:
    def __init__(self):
        self.done = []
        #: ``[(obj, reason), ...]``
        self.refused = []


# Where a check failed: a failed condition is shown as a disabled button,
# anything earlier hides the transition.
STATE, PERMS, CONDITION = 'state', 'perms', 'condition'


def _person(user):
    return user if user is not None and user.is_authenticated else None


def max_subflow_depth():
    """``GT_FLOWS_MAX_SUBFLOW_DEPTH``: how deep subflows may nest (10)."""
    return int(getattr(settings, 'GT_FLOWS_MAX_SUBFLOW_DEPTH', 10))


class Run:
    """One change of one instance, inside its transaction: the tokens move,
    the actions run, the log is written; :meth:`finish` saves it all.

    Activities talk to the engine through it (``move``, ``fork``, ``join``,
    ``start_subflow``).

    Moving a token puts it on its target at once (``arrive``: its
    ``on_enter`` actions run), but the work of that target (``act``) waits
    in a queue that the outermost ``act`` drains in a loop. An activity that
    moves a token therefore returns before the next one starts, the Python
    stack stays flat however long a chain of automatic activities is, and
    :attr:`MAX_STEPS` is what stops a loop. The queue is depth-first: what
    an activity starts runs before the activities queued earlier.
    """

    #: Moves one run may make before it is taken for a loop.
    MAX_STEPS = 500

    def __init__(self, flow, instance, obj, user=None, request=None, data=None,
                 comment='', notify_parent=True):
        self.flow = flow
        self.instance = instance
        self.obj = obj
        self.user = user
        self.request = request
        self.data = data or {}
        self.comment = comment
        self.notify_parent = notify_parent
        self.old_state = instance.state
        self.steps = 0
        #: ``act`` is draining the queue; ``_pending`` collects what the
        #: activity under way queues: ``(token id, activity, depth)``.
        self._acting = False
        self._pending = []

    def context(self, transition=None, activity=None, data=None, task=None):
        return ActionContext(obj=self.obj, user=self.user,
                             data=self.data if data is None else data,
                             variables=self.instance.variables, request=self.request,
                             flow=self.flow, instance=self.instance,
                             transition=transition, activity=activity, task=task)

    # -- tokens ---------------------------------------------------------------------
    def new_token(self, activity, scope=()):
        self.instance.token_seq += 1
        token = {'id': self.instance.token_seq, 'activity': activity,
                 'status': 'active', 'scope': list(scope)}
        self.instance.tokens.append(token)
        return token

    def token(self, token_id):
        return next((token for token in self.instance.tokens
                     if token['id'] == token_id), None)

    def remove(self, token):
        self.instance.tokens = [item for item in self.instance.tokens
                                if item['id'] != token['id']]

    def discard(self, token):
        """Drop ``token`` and whatever its activity left waiting for it."""
        activity = self.flow.activities.get(token['activity'])
        if activity is not None:
            activity.leave(self, token)
        self.remove(token)

    def log(self, kind, name, source, target, data=None, comment=''):
        return FlowTransitionLog.objects.create(
            instance=self.instance, kind=kind, transition=name, source=source,
            target=target, user=_person(self.user), comment=comment,
            data=json_safe(data or {}))

    # -- moving ---------------------------------------------------------------------
    def arrive(self, token, target):
        """Put ``token`` on ``target`` and run its ``on_enter`` actions."""
        activity = self.flow.activities[target]
        self.steps += 1
        if self.steps > self.MAX_STEPS:
            raise ImproperlyConfigured(
                '%s: more than %d moves in one run, around %r: the automatic '
                'activities make a loop' % (self.flow.name, self.MAX_STEPS, target))
        for key in ('due', 'signal', 'error', 'tasks', 'child'):
            token.pop(key, None)
        if token['activity'] != target:  # not a start nor a retry
            self.instance.visit += 1
        token.update(activity=target, status='active')
        self.instance.entered_at = timezone.now()
        if isinstance(activity, State):
            deadline = self.flow.deadline_for(target)
            if deadline is not None:
                due = deadline.due(self.context(activity=activity))
                token['due'] = due.isoformat() if due else None
        run_actions(self.flow.on_enter.get(target, []) + activity.on_enter,
                    self.context(activity=activity))

    def act(self, token, depth=0):
        """Do the work of the activity ``token`` stands on, and of whatever
        it moves on to, before returning.

        Called while another activity works, it only queues the token: the
        outermost call runs the queue (see the class docstring)."""
        item = (token['id'], token['activity'], depth)
        if self._acting:
            self._pending.append(item)
            return
        self._acting = True
        queue = deque([item])
        try:
            while queue:
                token_id, activity_id, depth = queue.popleft()
                current = self.token(token_id)
                if current is None or current['activity'] != activity_id \
                        or current['status'] != 'active':
                    continue  # discarded or moved by another branch meanwhile
                self._pending = []
                if self._act(current, depth):
                    queue.extendleft(reversed(self._pending))
        finally:
            self._acting = False
            self._pending = []

    def _act(self, token, depth):
        """One activity: a state chains its automatic transitions; the others
        run in a savepoint -- one that fails leaves the token in error instead
        of undoing the whole run. False when it failed."""
        activity = self.flow.activities[token['activity']]
        if isinstance(activity, State):
            self.chain(token, depth)
            return True
        tokens = copy.deepcopy(self.instance.tokens)
        variables = copy.deepcopy(self.instance.variables)
        seq = self.instance.token_seq
        try:
            with transaction.atomic():
                activity.enter(self, token)
        except ImproperlyConfigured:
            raise
        except Exception as error:
            # The savepoint undid the database; undo the instance in memory.
            # What the activity queued is undone with it.
            self.instance.tokens = tokens
            self.instance.variables = variables
            self.instance.token_seq = seq
            self.fail(self.token(token['id']), error)
            return False
        return True

    def enter(self, token, target, depth=0):
        self.arrive(token, target)
        self.act(token, depth)

    def move(self, token, target, kind='activity', data=None, depth=0):
        """Move ``token`` on from an activity that is done with it."""
        source = token['activity']
        activity = self.flow.activities[source]
        activity.leave(self, token)
        run_actions(self.flow.on_exit.get(source, []) + activity.on_exit,
                    self.context(activity=activity))
        self.log(kind, target, source, target, data)
        self.enter(token, target, depth)

    def transition(self, token, transition, data=None, comment='', kind='transition',
                   depth=0):
        """Move ``token`` along ``transition``, already checked."""
        source, target = token['activity'], transition.target
        moved = source != target
        context = self.context(transition=transition, data=data)
        signal = {'flow': self.flow, 'obj': self.obj, 'instance': self.instance,
                  'transition': transition, 'user': self.user, 'source': source,
                  'target': target, 'kind': kind}
        signals.pre_transition.send(sender=type(self.flow), **signal)
        actions = transition.actions
        if moved:
            activity = self.flow.activities[source]
            actions = self.flow.on_exit.get(source, []) + activity.on_exit + actions
            target_activity = self.flow.activities[target]
            # on_enter of the target runs in arrive(), after these.
            assigns = actions + self.flow.on_enter.get(target, []) \
                + target_activity.on_enter
        else:
            assigns = actions
        if not transition.keep_assignment and not any(
                getattr(action, 'assigns', False) for action in assigns):
            self.instance.assigned_to = None
            self.instance.assigned_group = None
        if moved:
            self.flow.activities[source].leave(self, token)
        run_actions(actions, context)
        if moved:
            self.arrive(token, target)
        self.sync()
        self.log(kind, transition.name, source, target, data, comment)
        signals.post_transition.send(sender=type(self.flow), **signal)
        if moved:
            self.act(token, depth)

    def chain(self, token, depth=0):
        """Run the first automatic transition out of the token's state whose
        condition holds, and so on from where it lands."""
        for transition in self.flow.transitions:
            if not transition.auto:
                continue
            ok, _reason, _where = self.flow._check(
                transition, self.obj, self.user, [token['activity']], self.instance,
                system=True)
            if not ok:
                continue
            if depth >= self.flow.max_auto_steps:
                raise ImproperlyConfigured(
                    '%s: more than %d automatic transitions in a row, from %r'
                    % (self.flow.name, self.flow.max_auto_steps, token['activity']))
            self.transition(token, transition, {}, kind='auto', depth=depth + 1)
            return

    def fail(self, token, error):
        logger.warning('Flow %s, instance %s: %s failed: %s', self.flow.name,
                       self.instance.pk, token['activity'], error)
        token['status'] = 'error'
        token['error'] = str(error) or type(error).__name__
        self.instance.status = ERROR
        self.instance.error = '%s: %s' % (token['activity'], token['error'])
        self.log('error', token['activity'], token['activity'], token['activity'],
                 {'error': token['error'], 'exception': type(error).__name__})

    # -- parallel -------------------------------------------------------------------
    def fork(self, token, parallel):
        key = '%s#%d' % (parallel.id, token['id'])
        scope = token.get('scope', []) + [key]
        self.remove(token)
        for branch in parallel.branches:
            child = self.new_token(parallel.id, scope)
            self.move(child, branch, data={'branch': branch})

    def join(self, token, join):
        scope = token.get('scope') or []
        if not scope:
            raise FlowError('%s: a join outside any parallel' % join.id)
        key = scope[-1]
        parallel = self.flow.activities.get(key.split('#')[0])
        token['status'] = 'joined'
        arrived = [item for item in self.instance.tokens
                   if item['activity'] == join.id and item['status'] == 'joined'
                   and (item.get('scope') or [None])[-1] == key]
        total = len(getattr(parallel, 'branches', ())) or len(arrived)
        needed = total if join.wait_for == 'all' else min(int(join.wait_for), total)
        if len(arrived) < needed:
            return
        for item in list(self.instance.tokens):
            if key in (item.get('scope') or []) and item not in arrived:
                self.discard(item)  # a branch still under way: cancelled
        for item in arrived:
            self.remove(item)
        if join.next is None:
            raise FlowError('%s has no next activity' % join.id)
        follower = self.new_token(join.id, scope[:-1])
        self.move(follower, join.next, data={'joined': len(arrived)})

    # -- subflows -------------------------------------------------------------------
    def subflow_depth(self):
        """How many parents the instance has, counted up to one past the
        ``GT_FLOWS_MAX_SUBFLOW_DEPTH`` limit."""
        limit = max_subflow_depth()
        depth, parent_id = 0, self.instance.parent_id
        while parent_id is not None and depth <= limit:
            depth += 1
            parent_id = FlowInstance.objects.filter(pk=parent_id).values_list(
                'parent_id', flat=True).first()
        return depth

    def start_subflow(self, token, subflow):
        child_flow = get_flow(subflow.flow, site=self.instance.site)
        if child_flow is None:
            raise FlowError('%s: no flow named %r' % (subflow.id, subflow.flow))
        # A subflow runs in the same transaction and Python call as its parent,
        # and every child is a new instance, so the steps of one run do not
        # count it: flows that start each other (A -> B -> A on other objects)
        # are stopped by their depth.
        if self.subflow_depth() + 1 > max_subflow_depth():
            raise FlowError('%s: more than %d nested subflows'
                            % (subflow.id, max_subflow_depth()))
        context = self.context(activity=subflow)
        obj = self.obj
        if callable(subflow.obj):
            obj = subflow.obj(context)
        elif isinstance(subflow.obj, str) and subflow.obj.startswith('field:'):
            obj = getattr(self.obj, subflow.obj[len('field:'):])
        variables = subflow.variables(context) if callable(subflow.variables) \
            else dict(subflow.variables or {})
        if child_flow.get_instance(obj, create=False) is not None:
            raise FlowError('%s: %s already runs %s' % (subflow.id, obj,
                                                        child_flow.name))
        child = child_flow.start(obj, self.user, variables=variables,
                                 request=self.request, parent=self.instance,
                                 parent_token=token['id'], notify_parent=False)
        token['child'] = child.pk
        if child.status == COMPLETED:
            self.child_done(token, subflow, child)

    def child_done(self, token, subflow, child):
        self.instance.variables[subflow.id] = child.variables
        self.move(token, subflow.target(child), data={'child': child.pk,
                                                      'ended_in': child.state})

    # -- saving ---------------------------------------------------------------------
    def sync(self):
        """``state``, ``status`` and ``due_at`` from the tokens."""
        instance = self.instance
        tokens = instance.tokens
        if len(tokens) == 1:
            instance.state = tokens[0]['activity']
        elif tokens:
            scopes = [token.get('scope') or [] for token in tokens]
            root = next((scope[0] for scope in scopes if scope), None)
            instance.state = root.split('#')[0] if root else tokens[0]['activity']
        dues = [to_datetime(token['due']) for token in tokens if token.get('due')]
        instance.due_at = min(dues) if dues else None
        if instance.status in (SUSPENDED, TERMINATED):
            return
        if any(token['status'] == 'error' for token in tokens):
            instance.status = ERROR
            return
        instance.error = ''
        finished = all(self.flow.is_final(token['activity']) for token in tokens)
        if finished and instance.status != COMPLETED:
            instance.status = COMPLETED
            instance.completed_at = timezone.now()
        elif not finished:
            instance.status = RUNNING
            instance.completed_at = None

    def finish(self):
        self.sync()
        instance = self.instance
        instance.variables = json_safe(instance.variables)
        instance.save()
        if instance.state != self.old_state:
            signals.flow_state_changed.send(sender=type(self.flow), flow=self.flow,
                                            instance=instance, old=self.old_state,
                                            new=instance.state)
            self.old_state = instance.state
        if (instance.status == COMPLETED and instance.parent_id
                and self.notify_parent):
            parent = instance.parent
            flow_for_instance(parent).child_completed(parent, instance)
        return instance


class Flow:
    #: Registry key; defaults to ``<app_label>.<ClassName>``.
    name = None
    title = ''
    model = None
    #: Instances stay with the version they started with; several classes
    #: may register one name with different versions.
    version = 1
    #: The FlowDefinition it was built from, for a JSON flow.
    definition = None
    #: ``[(value, label), ...]`` and :mod:`~djgentelella.flows.activities`.
    states = ()
    initial = None
    transitions = ()
    #: States no transition leaves -- not even a ``'*'`` one. When ``None``,
    #: a state is final when no transition can leave it (``'*'`` included).
    final_states = None
    #: ``{state: [action, ...]}``, run by any transition entering / leaving it.
    on_enter = {}
    on_exit = {}
    #: ``{state: Deadline(...)}``.
    deadlines = {}
    #: The variables a new instance starts with.
    variables = {}
    #: Automatic transitions one run may chain before it is taken for a loop.
    max_auto_steps = 10
    #: Who may hand an object to another user or group.
    reassign_perms = ['gtflows.change_flowinstance']
    #: Who may suspend, resume, terminate and retry instances.
    control_perms = ['gtflows.change_flowinstance']

    def __init__(self, **attributes):
        for key, value in attributes.items():
            setattr(self, key, value)
        if self.model is None:
            raise ImproperlyConfigured('%s has no model' % type(self).__name__)
        if self.name is None:
            self.name = '%s.%s' % (self.model._meta.app_label, type(self).__name__)
        self.activities = {}
        for item in self.states:
            activity = item if not isinstance(item, (tuple, list)) else State(*item)
            if activity.id in self.activities:
                raise ImproperlyConfigured('%s: activity %r is declared twice' % (
                    self.name, activity.id))
            self.activities[activity.id] = activity
        self.state_labels = {key: activity.label
                             for key, activity in self.activities.items()}
        if self.initial not in self.state_labels:
            raise ImproperlyConfigured('%s: initial %r is not a state' % (
                self.name, self.initial))
        seen = set()
        for transition in self.transitions:
            if transition.name in seen:
                raise ImproperlyConfigured('%s: transition %r is declared twice' % (
                    self.name, transition.name))
            seen.add(transition.name)
            unknown = [state for state in transition.source + [transition.target]
                       if state != ANY_STATE and state not in self.state_labels]
            if transition.target == ANY_STATE:
                unknown.append(ANY_STATE)
            if unknown:
                raise ImproperlyConfigured('%s: transition %r uses unknown states %s'
                                           % (self.name, transition.name, unknown))
            if transition.auto and transition.form:
                raise ImproperlyConfigured(
                    '%s: automatic transition %r cannot have a form'
                    % (self.name, transition.name))
        unknown = [state for state in self.final_states or ()
                   if state not in self.state_labels]
        for name, mapping in (('on_enter', self.on_enter), ('on_exit', self.on_exit),
                              ('deadlines', self.deadlines)):
            unknown += ['%s[%r]' % (name, state) for state in mapping
                        if state not in self.state_labels]
        for activity in self.activities.values():
            unknown += ['%s -> %r' % (activity.id, target)
                        for target, _label, _kind in activity.routes()
                        if target not in self.state_labels]
        if unknown:
            raise ImproperlyConfigured('%s: unknown states %s' % (self.name, unknown))
        for state in self.activities:
            deadline = self.deadline_for(state)
            if deadline is None or deadline.transition is None:
                continue
            transition = self.get_transition(deadline.transition)
            if transition is None or not self.leaves(transition, state):
                raise ImproperlyConfigured(
                    '%s: the deadline of %r runs %r, which does not leave it'
                    % (self.name, state, deadline.transition))

    def __str__(self):
        return str(self.title or self.name)

    # -- lookups ----------------------------------------------------------------
    def get_transition(self, name):
        for transition in self.transitions:
            if transition.name == name:
                return transition
        return None

    def state_label(self, state):
        return self.state_labels.get(state, state)

    def deadline_for(self, state):
        activity = self.activities.get(state)
        return self.deadlines.get(state) or getattr(activity, 'deadline', None)

    def is_final(self, state):
        activity = self.activities.get(state)
        if activity is not None and not isinstance(activity, State):
            return False
        if self.final_states is not None:
            return state in self.final_states
        return not any(self.leaves(transition, state)
                       for transition in self.transitions)

    def leaves(self, transition, state):
        """Whether ``transition`` may start from ``state``.

        ``'*'`` means any state but the transition's own target and the
        declared final states.
        """
        if state in transition.source:
            return True
        return (transition.from_any_state and state != transition.target
                and not (self.final_states is not None and state in self.final_states))

    def binds(self, instance):
        """Whether ``instance`` runs this very version of the flow."""
        definition = self.definition.pk if self.definition is not None else None
        return (instance.version == self.version
                and instance.definition_id == definition)

    def _bound(self, obj):
        """``(flow, instance)``: the version of the flow the object's instance
        started with -- this one, unless a newer version was published."""
        instance = self.get_instance(obj, create=False)
        if instance is not None and not self.binds(instance):
            return flow_for_instance(instance), instance
        return self, instance

    # -- object keys --------------------------------------------------------------
    def _uuid_pk(self):
        return isinstance(self.model._meta.pk, models.UUIDField)

    def object_key(self, obj):
        """How ``obj`` is stored in ``FlowInstance.object_id``.

        UUIDs as 32 hex digits: that is what SQLite and MySQL hold, and what a
        database-side cast of the primary key can be normalized to.
        """
        pk = obj.pk
        return pk.hex if self._uuid_pk() else str(pk)

    def _key_expression(self):
        key = Cast('pk', CharField())
        if self._uuid_pk():
            # PostgreSQL casts a uuid with hyphens, SQLite/MySQL store hex.
            key = Replace(key, Value('-'), Value(''))
        return key

    def annotate_state(self, queryset):
        """Add ``flow_key``, ``flow_state`` (initial when no instance),
        ``flow_status`` and ``flow_due_at``."""
        if 'flow_state' in queryset.query.annotations:
            return queryset
        instances = FlowInstance.objects.filter(
            flow=self.name, content_type=self.content_type(),
            object_id=OuterRef('flow_key'))
        return queryset.annotate(flow_key=self._key_expression()).annotate(
            flow_state=Coalesce(Subquery(instances.values('state')[:1]),
                                Value(self.initial)),
            flow_status=Coalesce(Subquery(instances.values('status')[:1]),
                                 Value(RUNNING)),
            flow_due_at=Subquery(instances.values('due_at')[:1]))

    def _assigned_q(self, user):
        assigned = FlowInstance.objects.filter(
            flow=self.name, content_type=self.content_type(),
            object_id=OuterRef('flow_key')).filter(
            Q(assigned_to=user) | Q(assigned_group__in=user.groups.all()))
        return Q(Exists(assigned))

    # -- reach ----------------------------------------------------------------------
    def view_permission(self):
        opts = self.model._meta
        return '%s.view_%s' % (opts.app_label, opts.model_name)

    def base_queryset(self):
        return self.model._default_manager.all()

    def get_queryset(self, user):
        """The objects ``user`` may reach through this flow (annotated).

        Override to narrow it, e.g. ``super().get_queryset(user)
        .filter(owner=user)``.
        """
        queryset = self.annotate_state(self.base_queryset())
        if not user.is_authenticated:
            return queryset.none()
        if user.has_perm(self.view_permission()):
            return queryset
        return queryset.filter(Q(flow_state__in=self.actionable_states(user))
                               | self._assigned_q(user))

    # -- instances --------------------------------------------------------------
    def content_type(self):
        return ContentType.objects.get_for_model(self.model)

    def _lookup(self, obj):
        return {'flow': self.name, 'content_type': self.content_type(),
                'object_id': self.object_key(obj)}

    def get_instance(self, obj, create=True, user=None, request=None):
        if not create:
            return FlowInstance.objects.filter(**self._lookup(obj)).first()
        return self.start(obj, user, request=request)

    def initial_variables(self):
        return copy.deepcopy(dict(self.variables or {}))

    def start(self, obj, user=None, variables=None, request=None, parent=None,
              parent_token=None, notify_parent=True):
        """The object's instance, started on the initial activity if it had
        none: its ``on_enter`` actions run, and whatever follows by itself.
        An object that already has one keeps it as it is.

        Starting checks no permission (there is no transition to check):
        without ``user`` it is a start by the system, logged without a user,
        and the automatic transitions it reaches run as the system too.
        """
        with transaction.atomic():
            instance, created = FlowInstance.objects.get_or_create(
                **self._lookup(obj), defaults={
                    'state': self.initial, 'version': self.version,
                    'definition': self.definition,
                    'variables': json_safe({**self.initial_variables(),
                                            **(variables or {})}),
                    'parent': parent, 'parent_token': parent_token,
                    'site': (get_current_site(request) if request is not None
                             else getattr(self.definition, 'site', None))})
            if not created:
                return instance
            run = Run(self, instance, obj, user, request, notify_parent=notify_parent)
            run.old_state = ''
            token = run.new_token(self.initial)
            run.enter(token, self.initial)
            return run.finish()

    def state(self, obj):
        instance = self.get_instance(obj, create=False)
        return instance.state if instance else self.initial

    def active_states(self, instance):
        """The activities whose tokens are waiting (initial when no instance)."""
        if instance is None:
            return [self.initial]
        return [token['activity'] for token in instance.active_tokens()]

    def states_for(self, objects):
        """``{pk: state}`` of many objects, in one query."""
        objects = list(objects)
        keys = {self.object_key(obj): obj.pk for obj in objects}
        found = dict(FlowInstance.objects.filter(
            flow=self.name, content_type=self.content_type(),
            object_id__in=list(keys)).values_list('object_id', 'state'))
        return {pk: found.get(key, self.initial) for key, pk in keys.items()}

    def history(self, obj):
        instance = self.get_instance(obj, create=False)
        if instance is None:
            return FlowTransitionLog.objects.none()
        return instance.log.select_related('user')

    def tasks(self, obj):
        instance = self.get_instance(obj, create=False)
        if instance is None:
            return Task.objects.none()
        return instance.tasks.all()

    # -- authorization ----------------------------------------------------------
    def may_attempt(self, transition, user):
        """Whether ``user`` holds what ``transition`` asks of people."""
        if transition.auto or user is None or not user.is_authenticated:
            return False
        if transition.perms and not user.has_perms(transition.perms):
            return False
        return True

    def _check(self, transition, obj, user, states, instance=None, system=False):
        """``(ok, reason, where it failed)``.

        ``states`` are the activities the instance waits in. ``system`` runs
        skip what is asked of people (perms) but not the state nor the
        condition.
        """
        if isinstance(states, str):
            states = [states]
        if instance is not None and instance.status not in LIVE:
            return False, _('The flow is %(status)s.') % {
                'status': instance.get_status_display().lower()}, STATE
        if not any(self.leaves(transition, state) for state in states):
            return False, _('%(transition)s cannot run from %(state)s.') % {
                'transition': transition.label,
                'state': ', '.join(str(self.state_label(state)) for state in states)
                or '-'}, STATE
        if not system and not self.may_attempt(transition, user):
            return False, _('You cannot run %(transition)s.') % {
                'transition': transition.label}, PERMS
        if transition.condition is not None:
            context = ActionContext(
                obj=obj, user=user, flow=self, instance=instance,
                transition=transition,
                variables=(instance.variables if instance is not None
                           else self.initial_variables()))
            try:
                if not evaluate(transition.condition, context):
                    return False, _('%(transition)s is not possible now.') % {
                        'transition': transition.label}, CONDITION
            except TransitionBlocked as blocked:
                return False, str(blocked), CONDITION
        return True, '', None

    def check(self, transition, obj, user, state=None):
        """``(ok, reason)``: whether ``user`` may run ``transition`` now and,
        when not, why."""
        flow, instance = self._bound(obj)
        if flow is not self:
            transition = flow.get_transition(getattr(transition, 'name', transition))
            if transition is None:
                return False, _('This version of the flow has no such transition.')
        states = flow.active_states(instance) if state is None else state
        ok, reason, _where = flow._check(transition, obj, user, states, instance)
        return ok, reason

    def can_run(self, transition, obj, user, state=None):
        return self.check(transition, obj, user, state)[0]

    def available_transitions(self, obj, user):
        flow, instance = self._bound(obj)
        states = flow.active_states(instance)
        return [transition for transition in flow.transitions
                if flow._check(transition, obj, user, states, instance)[0]]

    def transition_buttons(self, obj, user):
        """The transitions to show ``user``: the ones they can run, and the
        ones they hold the permission for but whose condition fails now --
        disabled, with the reason."""
        flow, instance = self._bound(obj)
        states = flow.active_states(instance)
        buttons = []
        for transition in flow.transitions:
            ok, reason, where = flow._check(transition, obj, user, states, instance)
            if not ok and where != CONDITION:
                continue
            buttons.append(Button(transition, disabled=not ok, reason=reason))
        return buttons

    # -- running ----------------------------------------------------------------
    def _lock_object(self, pk):
        queryset = self.model._default_manager.all()
        # PostgreSQL refuses FOR UPDATE on the nullable side of the outer joins
        # a manager's select_related() may add: lock only the model's own row
        # where the backend can say so (MariaDB cannot, and raises on of=).
        features = connections[router.db_for_write(self.model)].features
        if features.has_select_for_update_of:
            return queryset.select_for_update(of=('self',)).get(pk=pk)
        return queryset.select_for_update().get(pk=pk)

    def _lock_instance(self, obj, user=None, request=None):
        return FlowInstance.objects.select_for_update().get(
            pk=self.get_instance(obj, user=user, request=request).pk)

    def _locked(self, obj, user=None, request=None):
        """``(flow, instance, object)``, locked, in the flow version of the
        instance. Call inside a transaction."""
        instance = self._lock_instance(obj, user, request)
        flow = self if self.binds(instance) else flow_for_instance(instance)
        return flow, instance, flow._lock_object(obj.pk)

    def _refuse(self, reason, where):
        error = TransitionBlocked if where == CONDITION else TransitionNotAllowed
        raise error(reason)

    def run(self, obj, name, user=None, form=None, data=None, comment='',
            request=None, *, system=False):
        """Run transition ``name`` on ``obj``; return the FlowInstance.

        Everything happens in one transaction, on a fresh copy of the object
        locked with ``select_for_update()``: the permission and the condition
        are checked on it, the form (a ModelForm) is applied to it and saved,
        the actions run, the state changes and the log row is written -- or,
        when anything raises, none of it. Actions marked ``on_commit`` run
        once the transaction has committed.

        ``system=True`` runs it as the system, like an automatic transition
        or a ``Deadline``: the transition's ``perms`` are not checked, its
        source state and its ``condition`` are (with ``context.user`` None),
        and the log has no user. It takes no ``user``: passing one raises
        ``ValueError``, so a request's user never runs as the system by
        mistake. Without the flag a missing or anonymous ``user`` is refused
        (``TransitionNotAllowed``), as any user without the permissions.
        """
        if system and user is not None:
            raise ValueError('Flow.run(system=True) runs without a user: pass '
                             'user=None (got %r)' % (user,))
        with transaction.atomic():
            flow, instance, fresh = self._locked(obj, user, request)
            transition = flow.get_transition(name)
            if transition is None:
                raise TransitionNotAllowed('%s has no transition %r' % (flow.name,
                                                                        name))
            if form is not None:
                data = {key: value for key, value in form.cleaned_data.items()
                        if key not in transition.log_exclude}
            data = data or {}
            states = flow.active_states(instance)
            ok, reason, where = flow._check(transition, fresh, user, states, instance,
                                            system=system)
            if not ok:
                flow._refuse(reason, where)
            if isinstance(form, ModelForm):
                form.instance = construct_instance(
                    form, fresh, form._meta.fields, form._meta.exclude)
                fresh = form.save()
            if transition.variables:
                names = data if transition.variables is True else transition.variables
                instance.variables.update(json_safe(
                    {key: data[key] for key in names if key in data}))
            token = next(token for token in instance.active_tokens()
                         if flow.leaves(transition, token['activity']))
            run = Run(flow, instance, fresh, user, request, data, comment)
            run.transition(token, transition, data, comment)
            run.finish()
        return instance

    def evaluate(self, obj, user=None):
        """Run the automatic transitions the object's current state allows
        -- after the object changed outside the flow, for example."""
        with transaction.atomic():
            flow, instance, fresh = self._locked(obj, user)
            if instance.status not in LIVE:
                return instance
            run = Run(flow, instance, fresh, user)
            for token in list(instance.active_tokens()):
                if isinstance(flow.activities.get(token['activity']), State):
                    run.chain(token)
            run.finish()
        return instance

    def update_variables(self, obj, values, user=None, comment=''):
        """Merge ``values`` into the instance variables, logged."""
        with transaction.atomic():
            flow, instance, fresh = self._locked(obj, user)
            values = json_safe(values)
            instance.variables.update(values)
            run = Run(flow, instance, fresh, user)
            run.log('variables', 'variables', instance.state, instance.state, values,
                    comment)
            run.finish()
        return instance

    def signal(self, obj, name, data=None, user=None):
        """Wake the ``wait`` activities of the object waiting for signal
        ``name``; ``data`` is merged into the variables. Returns how many
        woke up (0 when nothing waited for it)."""
        with transaction.atomic():
            instance = self.get_instance(obj, create=False)
            if instance is None:
                return 0
            flow, instance, fresh = self._locked(obj, user)
            if instance.status not in LIVE:
                raise TransitionNotAllowed(_('The flow is %(status)s.') % {
                    'status': instance.get_status_display().lower()})
            run = Run(flow, instance, fresh, user)
            woken = [token for token in instance.active_tokens()
                     if token.get('signal') == name]
            if data:
                instance.variables.update(json_safe(data))
            for token in woken:
                activity = flow.activities[token['activity']]
                run.move(token, activity.next, kind='signal',
                         data={'signal': name, **json_safe(data or {})})
            run.finish()
        return len(woken)

    def run_many(self, objects, name, user, comment=''):
        """Run ``name`` on each object, each in its own transaction.

        Returns a :class:`BulkResult`; a refusal stops only its object.
        """
        transition = self.get_transition(name)
        if transition is None or not transition.bulkable:
            raise TransitionNotAllowed(_('%(name)s cannot run on many objects.') % {
                'name': name})
        result = BulkResult()
        for obj in objects:
            try:
                self.run(obj, name, user, comment=comment)
            except TransitionNotAllowed as refusal:
                result.refused.append((obj, str(refusal)))
            else:
                result.done.append(obj)
        return result

    def bulk_transitions(self, user):
        return [transition for transition in self.transitions
                if transition.bulkable and self.may_attempt(transition, user)]

    # -- tasks and subflows -----------------------------------------------------------
    def _object_of(self, instance):
        pk = self.model._meta.pk.to_python(instance.object_id)
        return self._lock_object(pk)

    def task_done(self, task, user=None):
        """A task of the instance closed: the ``human_task`` waiting for it
        decides whether the flow moves on."""
        instance = FlowInstance.objects.select_for_update().get(pk=task.instance_id)
        if instance.status not in LIVE:
            raise TransitionNotAllowed(_('The flow is %(status)s.') % {
                'status': instance.get_status_display().lower()})
        try:
            obj = self._object_of(instance)
        except self.model.DoesNotExist:
            raise TaskNotAllowed(_('The object of this task no longer exists.')) \
                from None
        run = Run(self, instance, obj, user)
        token = run.token(task.token)
        activity = self.activities.get(task.activity)
        if token is None or token['status'] != 'active' \
                or token['activity'] != task.activity or activity is None:
            return instance  # the flow moved on meanwhile
        try:
            with transaction.atomic():
                activity.task_done(run, token, task)
        except FlowError as error:
            run.fail(token, error)
        return run.finish()

    def child_completed(self, instance, child):
        instance = FlowInstance.objects.select_for_update().get(pk=instance.pk)
        if instance.status not in LIVE:
            return instance
        try:
            obj = self._object_of(instance)
        except self.model.DoesNotExist:
            return instance  # the parent's object went away meanwhile
        run = Run(self, instance, obj)
        token = run.token(child.parent_token)
        activity = self.activities.get(token['activity']) if token else None
        if not isinstance(activity, Subflow):
            return instance
        try:
            with transaction.atomic():
                run.child_done(token, activity, child)
        except FlowError as error:
            run.fail(token, error)
        return run.finish()

    # -- control ------------------------------------------------------------------
    def can_control(self, user):
        return user is not None and user.is_authenticated and user.has_perms(
            self.control_perms)

    def _control(self, obj, user, kind, change, comment=''):
        with transaction.atomic():
            flow, instance, fresh = self._locked(obj, user)
            run = Run(flow, instance, fresh, user)
            data = change(flow, run, instance) or {}
            run.log(kind, kind, instance.state, instance.state, data, comment)
            run.finish()
        return instance

    def suspend(self, obj, user=None, comment=''):
        """Nothing moves a suspended instance: no transition, timer, signal
        nor task completion, until :meth:`resume`."""
        def change(flow, run, instance):
            if instance.status not in LIVE:
                raise TransitionNotAllowed(_('Only a running flow can be suspended.'))
            instance.status = SUSPENDED
        return self._control(obj, user, 'suspend', change, comment)

    def resume(self, obj, user=None, comment=''):
        def change(flow, run, instance):
            if instance.status != SUSPENDED:
                raise TransitionNotAllowed(_('The flow is not suspended.'))
            instance.status = RUNNING  # sync() puts it back in error if it was
        return self._control(obj, user, 'resume', change, comment)

    def terminate(self, obj, user=None, comment=''):
        """End the instance where it is: its open tasks are cancelled and its
        subflows terminated."""
        def change(flow, run, instance):
            if instance.status in (COMPLETED, TERMINATED):
                raise TransitionNotAllowed(_('The flow has ended already.'))
            for token in list(instance.tokens):
                run.discard(token)
            for task in instance.tasks.filter(state__in=Task.OPEN):
                task.cancel(user, comment)
            for child in instance.children.exclude(status__in=(COMPLETED,
                                                               TERMINATED)):
                child_flow = flow_for_instance(child)
                child_flow.terminate(child.content_object, user, comment)
            instance.status = TERMINATED
            instance.completed_at = timezone.now()
            instance.due_at = None
        return self._control(obj, user, 'terminate', change, comment)

    def retry(self, obj, user=None, comment=''):
        """Enter again the activities that failed."""
        def change(flow, run, instance):
            failed = [token for token in instance.tokens if token['status'] == 'error']
            if instance.status != ERROR or not failed:
                raise TransitionNotAllowed(_('Nothing failed: nothing to retry.'))
            instance.status = RUNNING
            for token in failed:
                run.enter(token, token['activity'])
            return {'activities': [token['activity'] for token in failed]}
        return self._control(obj, user, 'retry', change, comment)

    # -- timers ---------------------------------------------------------------------
    def _lock_due(self, pk, now):
        queryset = FlowInstance.objects.filter(pk=pk, due_at__lte=now,
                                               status__in=LIVE)
        features = connections[router.db_for_write(FlowInstance)].features
        if features.has_select_for_update_skip_locked:
            return queryset.select_for_update(skip_locked=True).first()
        return queryset.select_for_update().first()

    def run_deadline(self, instance_pk, now=None):
        """Process the timers of one instance past its ``due_at``: what
        happened (``'moved'``, ``'reminded'``, ``'cleared'``), or None.

        A ``wait`` goes on to its next activity. A state's deadline runs its
        actions, then its transition as the system; when nothing moves the
        object, the timer is cleared so it fires once.
        """
        now = now or timezone.now()
        with transaction.atomic():
            instance = self._lock_due(instance_pk, now)
            if instance is None:  # done meanwhile, or another worker has it
                return None
            pk = self.model._meta.pk.to_python(instance.object_id)
            obj = self.model._default_manager.filter(pk=pk).first()
            result = 'cleared'
            run = Run(self, instance, obj)
            timed = [token for token in instance.active_tokens() if token.get('due')]
            # When due_at is brought forward by hand, the earliest timers fire
            # then, even if their own date is later.
            earliest = min((to_datetime(token['due']) for token in timed),
                           default=None)
            due = [token for token in timed
                   if to_datetime(token['due']) == earliest
                   or to_datetime(token['due']) <= now]
            for token in due:
                token['due'] = None
                if obj is None:
                    continue
                run.obj = obj = self._lock_object(pk)
                activity = self.activities[token['activity']]
                if not isinstance(activity, State):
                    run.move(token, activity.next, kind='timeout')
                    result = 'moved'
                    continue
                deadline = self.deadline_for(token['activity'])
                if deadline is None:
                    continue
                transition = (self.get_transition(deadline.transition)
                              if deadline.transition else None)
                run_actions(deadline.actions, run.context(transition=transition))
                result = 'reminded'
                if transition is not None and self._check(
                        transition, obj, None, [token['activity']], instance,
                        system=True)[0]:
                    run.transition(token, transition, {}, kind='timeout')
                    result = 'moved'
            run.finish()
            return result

    # -- assignment -----------------------------------------------------------------
    def can_reassign(self, user):
        return user.is_authenticated and user.has_perms(self.reassign_perms)

    def assignment_actions(self, obj, user):
        """``{'claim': bool, 'release': bool, 'reassign': bool}`` for ``user``."""
        instance = self.get_instance(obj, create=False)
        assigned_to = instance.assigned_to_id if instance else None
        group = instance.assigned_group_id if instance else None
        return {
            'claim': bool(group and not assigned_to
                          and user.groups.filter(pk=group).exists()),
            'release': bool(assigned_to and assigned_to == user.pk),
            'reassign': self.can_reassign(user),
        }

    def _assignment(self, obj, user, action, comment, change):
        with transaction.atomic():
            flow, instance, fresh = self._locked(obj, user)
            if not self.assignment_actions(obj, user)[action]:
                raise TransitionNotAllowed(_('You cannot %(action)s it.') % {
                    'action': action})
            data = change(instance)
            run = Run(flow, instance, fresh, user)
            run.log(action, action, instance.state, instance.state, data, comment)
            run.finish()
        return instance

    def claim(self, obj, user, comment=''):
        """Take an object assigned to one of ``user``'s groups."""
        def change(instance):
            instance.assigned_to = user
        return self._assignment(obj, user, 'claim', comment, change)

    def release(self, obj, user, comment=''):
        """Give back what ``user`` claimed; it stays with the group."""
        def change(instance):
            instance.assigned_to = None
        return self._assignment(obj, user, 'release', comment, change)

    def reassign(self, obj, user, to_user=None, to_group=None, comment=''):
        def change(instance):
            instance.assigned_to = to_user
            instance.assigned_group = to_group
            return {'to_user': to_user, 'to_group': to_group}
        return self._assignment(obj, user, 'reassign', comment, change)

    # -- inbox ------------------------------------------------------------------
    def actionable_states(self, user):
        """States from which ``user`` could run some transition.

        A transition without ``perms`` counts only for users who may view
        the flow's objects. Conditions are not evaluated here: they need
        each object.
        """
        can_view = user.has_perm(self.view_permission())
        states = set()
        for transition in self.transitions:
            if not self.may_attempt(transition, user):
                continue
            if not transition.perms and not can_view:
                continue
            states.update(state for state in self.state_labels
                          if self.leaves(transition, state))
        return states

    def inbox(self, user):
        """Objects waiting for ``user``: in a state they can act on, or assigned
        to them or to one of their groups -- never in a final state nor in an
        instance that ended. Annotated with ``flow_state`` and ``flow_due_at``.
        """
        queryset = self.get_queryset(user)
        finals = [state for state in self.state_labels if self.is_final(state)]
        return queryset.filter(
            Q(flow_state__in=self.actionable_states(user)) | self._assigned_q(user)
        ).exclude(flow_state__in=finals).exclude(
            flow_status__in=(COMPLETED, TERMINATED))

    # -- diagram ------------------------------------------------------------------
    def as_graph(self):
        """The flow as ``{'nodes': [...], 'edges': [...]}``, plain JSON;
        a ``'*'`` transition becomes one edge per state it may leave, and
        every route of an activity (cases, branches, outcomes) an edge."""
        timeouts = {(state, self.deadline_for(state).transition)
                    for state in self.activities
                    if self.deadline_for(state) and self.deadline_for(state).transition}
        nodes = [{'id': key, 'label': str(activity.label), 'type': activity.type,
                  'initial': key == self.initial, 'final': self.is_final(key)}
                 for key, activity in self.activities.items()]
        edges = []
        for transition in self.transitions:
            for state in self.state_labels:
                if not self.leaves(transition, state):
                    continue
                edges.append({
                    'source': state, 'target': transition.target,
                    'name': transition.name, 'label': str(transition.label),
                    'auto': transition.auto,
                    # Reached only through '*': drawn from one "any state" node.
                    'any': transition.from_any_state
                    and state not in transition.source,
                    'timeout': (state, transition.name) in timeouts,
                })
        for key, activity in self.activities.items():
            for target, label, kind in activity.routes():
                edges.append({'source': key, 'target': target,
                              'name': '%s:%s' % (key, label or target),
                              'label': str(label), 'auto': True, 'any': False,
                              'timeout': kind == 'timeout', 'kind': kind})
        return {'nodes': nodes, 'edges': edges}

    def runtime(self, instance):
        """``{'active': [...], 'error': [...], 'completed': [...]}``: the
        activities of ``instance`` under way, failed, and already done, for
        the diagram."""
        if instance is None:
            return {'active': [self.initial], 'error': [], 'completed': []}
        active = [token['activity'] for token in instance.tokens
                  if token['status'] in ('active', 'joined')]
        error = [token['activity'] for token in instance.tokens
                 if token['status'] == 'error']
        visited = set()
        for source, target in instance.log.values_list('source', 'target'):
            visited.update((source, target))
        visited.add(self.initial)
        completed = [key for key in self.activities
                     if key in visited and key not in active and key not in error]
        return {'active': active, 'error': error, 'completed': completed}


# -- objects that go away ----------------------------------------------------------
#: Seconds between two looks at which models the published flows run on.
WATCH_REFRESH = 60
_watch = {'checked_at': None, 'busy': False}


def _object_deleted(sender, instance, **kwargs):
    forget_object(sender, instance.pk)


def watch_deletes(model):
    """Forget the flow instances of ``model``'s objects when they are deleted
    (:func:`~djgentelella.flows.models.forget_object`). Connected once per
    model, whatever flows run on it."""
    post_delete.connect(_object_deleted, sender=model, weak=False,
                        dispatch_uid='gtflows-delete-%s' % model._meta.label_lower)


def watch_definition_models(using=None, force=False):
    """:func:`watch_deletes` every model a ``FlowDefinition`` runs on.

    A JSON flow is only built in a process that uses it, so the engine does
    not wait for that: this runs when a process opens its first database
    connection (and again, at most every :data:`WATCH_REFRESH` seconds, when
    it opens another one), so a shell, a command or a worker that deletes an
    object also cleans its flows up. Errors -- the table does not exist yet,
    during the first migration -- are ignored.
    """
    now = timezone.now()
    checked = _watch['checked_at']
    if _watch['busy'] or (not force and checked is not None
                          and (now - checked).total_seconds() < WATCH_REFRESH):
        return
    _watch['busy'] = True
    try:
        labels = FlowDefinition.objects.using(using).values_list(
            'document__model', flat=True).distinct()
        for label in set(labels):
            try:
                watch_deletes(apps.get_model(label))
            except (LookupError, ValueError, TypeError):
                continue
        _watch['checked_at'] = now
    except DatabaseError:
        pass
    finally:
        _watch['busy'] = False


def _on_connection(sender, connection, **kwargs):
    if connection.alias == router.db_for_read(FlowDefinition) \
            and not connection.in_atomic_block:
        watch_definition_models(using=connection.alias)


@receiver(post_save, sender=FlowDefinition, dispatch_uid='gtflows-definition-saved')
def _definition_saved(sender, instance, **kwargs):
    model = instance.document.get('model') if isinstance(instance.document,
                                                         dict) else None
    try:
        watch_deletes(apps.get_model(model))
    except (LookupError, ValueError, TypeError, AttributeError):
        pass


def _connect_delete(flow):
    watch_deletes(flow.model)


def register_flow(flow_class):
    """Register a Flow subclass (also usable as a class decorator).

    Registering the same class again is a no-op; another class under a name
    and version already taken is an error, so two flows cannot silently
    replace each other. A class with a higher ``version`` starts the new
    instances; the older ones go on with the class they started with.
    """
    flow = flow_class()
    versions = _registry.setdefault(flow.name, {})
    existing = versions.get(flow.version)
    if existing is not None:
        if type(existing) is flow_class:
            return flow_class
        raise ImproperlyConfigured('Flow %r v%d is already registered by %s.%s' % (
            flow.name, flow.version, type(existing).__module__,
            type(existing).__name__))
    versions[flow.version] = flow
    _connect_delete(flow)
    return flow_class


def registered_flow_classes():
    """``{name: {version: Flow}}`` of the flows declared in Python; no query."""
    return {name: dict(versions) for name, versions in _registry.items()}


def active_definition(name, site=None):
    """The FlowDefinition that starts new instances of ``name``: active, of
    the site (else global), the highest version."""
    found = FlowDefinition.objects.filter(name=name, is_active=True).filter(
        site_q(site))
    # The site's own definitions win over the global ones (the Site rule).
    return found.order_by(models.F('site').asc(nulls_last=True), '-version').first()


def build(definition):
    """The Flow of a FlowDefinition, cached until it changes."""
    # The loader builds Flows; it imports this module.
    from djgentelella.flows.definitions import build_flow  # noqa: PLC0415 (circular)
    key = (definition.pk, definition.updated_at)
    flow = _built.get(key)
    if flow is None:
        flow = build_flow(definition.document, definition=definition)
        for old in [old for old in _built if old[0] == definition.pk]:
            del _built[old]
        _built[key] = flow
        _connect_delete(flow)
    return flow


def get_flow(name, version=None, site=None):
    """The flow called ``name``.

    Without ``version``, the one new instances start with: the active
    FlowDefinition of ``site`` (or global) with the highest version, else the
    highest version declared in Python. With ``version``, that one exactly.
    """
    if version is None:
        definition = active_definition(name, site)
        if definition is not None:
            return build(definition)
        versions = _registry.get(name)
        return versions[max(versions)] if versions else None
    python = _registry.get(name, {}).get(version)
    if python is not None:
        return python
    definition = FlowDefinition.objects.filter(name=name, version=version).filter(
        site_q(site)).order_by(models.F('site').asc(nulls_last=True)).first()
    return build(definition) if definition is not None else None


def flow_for_instance(instance):
    """The flow (and version) ``instance`` runs."""
    if instance.definition_id is not None:
        return build(instance.definition)
    versions = _registry.get(instance.flow, {})
    flow = versions.get(instance.version) or (versions[max(versions)] if versions
                                              else None)
    if flow is None:
        raise ImproperlyConfigured('No flow %r v%d for instance %s' % (
            instance.flow, instance.version, instance.pk))
    return flow


def get_flows():
    """``{name: Flow}``: the newest version of every flow declared in Python
    and of every active FlowDefinition."""
    found = {name: versions[max(versions)] for name, versions in _registry.items()}
    for name in FlowDefinition.objects.filter(is_active=True).values_list(
            'name', flat=True).distinct():
        flow = get_flow(name)
        if flow is not None:
            found[name] = flow
    return found


def current_site(request):
    return get_current_site(request) if request is not None else None


@receiver(signals.task_completed, dispatch_uid='gtflows-task-completed')
def _continue_flow(sender, task, user=None, **kwargs):
    """A task of a flow instance closed: move the flow on."""
    if task.instance_id is None or not task.activity:
        return
    instance = FlowInstance.objects.get(pk=task.instance_id)
    flow_for_instance(instance).task_done(task, user)


connection_created.connect(_on_connection, dispatch_uid='gtflows-watch-deletes')
