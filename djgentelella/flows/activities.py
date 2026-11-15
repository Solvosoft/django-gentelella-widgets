"""The kinds of activity a flow is made of, besides plain states.

A flow lists them in ``states``, next to ``(value, label)`` tuples (which are
:class:`State`). The engine keeps a *token* on each activity under way:

* :class:`State` -- waits for a person (or an automatic transition) to run
  one of the ``transitions`` that leave it;
* :class:`Switch` -- picks the first case whose condition holds;
* :class:`Wait` -- until a date, a delay, or a signal
  (``flow.signal(obj, name, data)``), whichever comes first;
* :class:`Parallel` / :class:`Join` -- branches under way at the same time,
  and the point where they meet again (all of them, or the first N);
* :class:`Subflow` -- starts another flow and waits for it to end;
* :class:`HumanTask` -- creates :class:`~djgentelella.flows.models.Task`\\ s
  and waits for their outcome;
* :class:`ActionActivity` -- runs actions, no person involved.

Everything but a ``State`` moves on by itself. When one of them raises -- an
action that fails, a switch no case matches -- its token is left in error and
the instance with it; ``flow.retry(obj)`` enters the activity again.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from djgentelella.flows.actions import render, run_actions, users
from djgentelella.flows.conditions import evaluate
from djgentelella.flows.models import Task
from djgentelella.flows.taskforms import BlockedTaskForm, get_task_form
from djgentelella.flows.tasks import create_task
from djgentelella.flows.utils import to_datetime, to_timedelta, value_at


class FlowError(Exception):
    """An activity cannot go on: its token is left in error."""


class Activity:
    type = ''
    #: Moves on by itself; never the target of a person's transition.
    automatic = True

    def __init__(self, id, label=None, on_enter=None, on_exit=None, help_text=''):
        self.id = id
        self.label = label or id.replace('_', ' ').capitalize()
        #: Actions run whenever a token enters / leaves the activity.
        self.on_enter = list(on_enter or [])
        self.on_exit = list(on_exit or [])
        self.help_text = help_text

    def __repr__(self):
        return '<%s %s>' % (type(self).__name__, self.id)

    def routes(self):
        """``[(target, label, kind), ...]``: where it may send a token, for
        the checks and the diagram. ``kind`` is ``'next'``, ``'case'``,
        ``'branch'``, ``'outcome'`` or ``'timeout'``."""
        return []

    def enter(self, run, token):
        """Do the activity's work for ``token``, which just arrived."""

    def leave(self, run, token):
        """``token`` goes away (moved on by a transition, cancelled):
        drop whatever the activity left waiting for it."""


class State(Activity):
    """A state: the token stays until a transition leaves it."""

    type = 'state'
    automatic = False

    def __init__(self, id, label=None, deadline=None, **kwargs):
        super().__init__(id, label, **kwargs)
        #: A :class:`~djgentelella.flows.base.Deadline`; ``Flow.deadlines``
        #: maps states to them as well.
        self.deadline = deadline


class Switch(Activity):
    """Goes to the target of the first case whose condition holds, or to
    ``default``. ``cases`` is ``[(condition, target), ...]`` (or dicts with
    ``condition`` and ``target``); see :mod:`djgentelella.flows.conditions`."""

    type = 'switch'

    def __init__(self, id, label=None, cases=(), default=None, **kwargs):
        super().__init__(id, label, **kwargs)
        self.cases = [(case['condition'], case['target']) if isinstance(case, dict)
                      else tuple(case) for case in cases]
        self.default = default

    def routes(self):
        found = [(target, str(getattr(condition, '__name__', '') or condition)
                  if not isinstance(condition, dict) else condition.get(
                      'function', 'condition'), 'case')
                 for condition, target in self.cases]
        if self.default:
            found.append((self.default, 'default', 'case'))
        return found

    def enter(self, run, token):
        context = run.context(activity=self)
        for condition, target in self.cases:
            if evaluate(condition, context):
                run.move(token, target, data={'case': target})
                return
        if self.default is None:
            raise FlowError('%s: no case holds and there is no default' % self.id)
        run.move(token, self.default, data={'case': 'default'})


class ActionActivity(Activity):
    """Runs ``actions`` and goes on to ``next``."""

    type = 'action'

    def __init__(self, id, label=None, actions=(), next=None, **kwargs):
        super().__init__(id, label, **kwargs)
        self.actions = list(actions)
        self.next = next

    def routes(self):
        return [(self.next, '', 'next')] if self.next else []

    def enter(self, run, token):
        run_actions(self.actions, run.context(activity=self))
        if self.next is None:
            raise FlowError('%s has no next activity' % self.id)
        run.move(token, self.next)


class Wait(Activity):
    """Waits until ``after`` (a duration, or a callable ``(context) ->
    datetime``), until the date in the variable ``until`` or until signal
    ``signal`` -- whichever comes first -- and goes on to ``next``.

    ``next`` is required: both the signal and the timeout move the token there,
    so a wait without it could never be left.

    A signal's ``data`` is merged into the variables.
    """

    type = 'wait'

    def __init__(self, id, label=None, after=None, until=None, signal=None,
                 next=None, **kwargs):
        super().__init__(id, label, **kwargs)
        if after is None and until is None and signal is None:
            raise ImproperlyConfigured('Wait %r waits for nothing: give it after, '
                                       'until or signal' % id)
        if not next:
            raise ImproperlyConfigured('Wait %r has no next activity: the signal '
                                       'and the timeout both go there' % id)
        self.after = after if callable(after) else to_timedelta(after)
        self.until = until
        self.signal = signal
        self.next = next

    def routes(self):
        return [(self.next, self.signal or '', 'timeout' if not self.signal
                 else 'next')]

    def due(self, context):
        if callable(self.after):
            return self.after(context)
        if self.after is not None:
            return timezone.now() + self.after
        if self.until is not None:
            return to_datetime(value_at(context.variables, self.until))
        return None

    def enter(self, run, token):
        due = self.due(run.context(activity=self))
        token['due'] = due.isoformat() if due else None
        token['signal'] = self.signal


class Parallel(Activity):
    """Starts one token per activity in ``branches``. They meet again at a
    :class:`Join`."""

    type = 'parallel'

    def __init__(self, id, label=None, branches=(), **kwargs):
        super().__init__(id, label, **kwargs)
        self.branches = list(branches)
        if len(self.branches) < 2:
            raise ImproperlyConfigured('Parallel %r needs two branches at least' % id)

    def routes(self):
        return [(branch, '', 'branch') for branch in self.branches]

    def enter(self, run, token):
        run.fork(token, self)


class Join(Activity):
    """Where the branches of a :class:`Parallel` meet: it goes on to ``next``
    once ``wait_for`` of them arrived -- ``'all'``, or a number; the
    branches still under way then are cancelled."""

    type = 'join'

    def __init__(self, id, label=None, wait_for='all', next=None, **kwargs):
        super().__init__(id, label, **kwargs)
        self.wait_for = wait_for
        self.next = next

    def routes(self):
        return [(self.next, '', 'next')] if self.next else []

    def enter(self, run, token):
        run.join(token, self)


class Subflow(Activity):
    """Starts flow ``flow`` and waits until it completes.

    It runs on the same object, or on ``obj`` (a callable ``(context) ->
    object`` or a ``'field:<path>'``). ``variables`` (a dict or a callable)
    are its initial variables. When it ends, its variables are copied into
    ``variables[<this activity's id>]`` and the token goes to
    ``outcomes[<the state it ended in>]``, or else to ``next``.
    """

    type = 'subflow'

    def __init__(self, id, label=None, flow=None, obj=None, variables=None,
                 next=None, outcomes=None, **kwargs):
        super().__init__(id, label, **kwargs)
        if not flow:
            raise ImproperlyConfigured('Subflow %r needs a flow' % id)
        self.flow = flow
        self.obj = obj
        self.variables = variables
        self.next = next
        self.outcomes = dict(outcomes or {})

    def routes(self):
        found = [(target, state, 'outcome') for state, target in self.outcomes.items()]
        if self.next:
            found.append((self.next, '', 'next'))
        return found

    def target(self, child):
        target = self.outcomes.get(child.state, self.next)
        if target is None:
            raise FlowError('%s: subflow ended in %r, which leads nowhere'
                            % (self.id, child.state))
        return target

    def enter(self, run, token):
        run.start_subflow(token, self)


class HumanTask(Activity):
    """Creates a task and waits for its outcome; ``outcomes`` maps each
    outcome to where the token goes (``next`` is the fallback).

    * ``title`` and ``description`` are templates (``object``, ``variables``...);
    * ``owners`` are recipients (``'field:approver'``, ``'user:ana'``, a
      callable...) and ``groups`` group names (or a callable returning them);
    * ``priority`` 1-5; ``due`` a duration or callable ``(context) -> datetime``;
    * ``on_expire``: ``{'outcome': 'reject'}`` (decide for them),
      ``{'escalate': {'owners': [...], 'groups': [...], 'priority': 1,
      'due': <duration>}}`` (hand it over) and/or ``{'notify': 'text'}``.
      An outcome ``'expired'`` in ``outcomes`` catches a task that simply
      expires.

    **Several approvers.** With ``each=True`` every person (the owners and
    the members of the groups) gets a task of their own, and the activity is
    decided by ``min`` of them -- a number, ``'all'`` or ``'majority'`` --
    giving the same outcome, tried in the order of ``outcomes``. Once no
    outcome can reach ``min`` any more, the last outcome wins (a veto). The
    tasks still open are cancelled.

    The outcome is kept in ``variables['<id>_outcome']``, and the data a task
    is completed with is merged into the variables.

    ``form`` is the form the person fills in to complete the task: the name
    of a form registered with
    :func:`~djgentelella.flows.taskforms.register_task_form`, or the class.
    The task page shows it, validates it and its ``cleaned_data`` is the
    task's data -- so it lands in the variables.
    """

    type = 'human_task'

    def __init__(self, id, label=None, title=None, description='', owners=(),
                 groups=(), outcomes=None, next=None, priority=3, due=None,
                 on_expire=None, each=False, min='all', form=None, **kwargs):
        super().__init__(id, label, **kwargs)
        #: The form class, or None; resolved now, so an unknown name fails
        #: when the flow is built (and published), not when a task completes.
        #: A stored JSON flow whose form is not allowed keeps it here instead,
        #: and the activity refuses to create the task (see ``enter``).
        self.blocked_form = form if isinstance(form, BlockedTaskForm) else None
        self.form = get_task_form(form) if form and not self.blocked_form \
            else None
        self.title = title or str(self.label)
        self.description = description
        self.owners = owners
        self.groups = groups
        self.outcomes = dict(outcomes or {'approve': next, 'reject': next})
        self.next = next
        self.priority = priority
        self.due = due if callable(due) else to_timedelta(due)
        self.on_expire = dict(on_expire or {})
        self.each = each
        self.min = min
        if not self.choices():
            raise ImproperlyConfigured('HumanTask %r has no outcomes' % id)

    def choices(self):
        return [outcome for outcome in self.outcomes if outcome != 'expired']

    def routes(self):
        found = [(target, outcome, 'timeout' if outcome == 'expired' else 'outcome')
                 for outcome, target in self.outcomes.items() if target]
        if self.next and self.next not in self.outcomes.values():
            found.append((self.next, '', 'next'))
        return found

    def _expire_config(self, context):
        config = dict(self.on_expire)
        if 'escalate' in config:
            escalate = dict(config['escalate'])
            escalate['users'] = [user.pk for user in users(
                escalate.pop('owners', ()), context)]
            escalate['groups'] = list(escalate.get('groups', ()))
            if escalate.get('due') is not None:
                escalate['due'] = to_timedelta(escalate['due']).total_seconds()
            config['escalate'] = escalate
        return config

    def enter(self, run, token):
        if self.blocked_form is not None:
            # Checked on every entry: CallableNotAllowed (logged) leaves the
            # activity in error; once allowed, the task gets the form.
            self.form = self.blocked_form.resolve()
        context = run.context(activity=self)
        owners = users(self.owners, context) if self.owners else []
        groups = self.groups(context) if callable(self.groups) else list(self.groups)
        due = self.due(context) if callable(self.due) else (
            timezone.now() + self.due if self.due else None)
        common = dict(obj=run.obj, title=render(self.title, context),
                      description=render(self.description, context), due=due,
                      priority=self.priority, instance=run.instance,
                      outcome_choices=self.choices(), activity=self.id,
                      token=token['id'], on_expire=self._expire_config(context),
                      user=run.user)
        if self.each:
            people = {user.pk: user for user in owners}
            for user in get_user_model().objects.filter(groups__name__in=groups,
                                                        is_active=True):
                people.setdefault(user.pk, user)
            if not people:
                raise FlowError('%s: nobody to give the tasks to' % self.id)
            tasks = [create_task(potential_owners=[user], **common)
                     for user in people.values()]
        else:
            if not owners and not groups:
                raise FlowError('%s: the task has no owners and no groups' % self.id)
            tasks = [create_task(potential_owners=owners, groups=groups, **common)]
        token['tasks'] = [task.pk for task in tasks]

    def tasks(self, run, token):
        return Task.objects.filter(instance=run.instance, activity=self.id,
                                   token=token['id'])

    def needed(self, total):
        if self.min == 'all':
            return total
        if self.min == 'majority':
            return total // 2 + 1
        return min(int(self.min), total)

    def decide(self, run, token, task):
        """The outcome the activity takes now that ``task`` closed, or None
        to keep waiting."""
        if task.state == Task.EXPIRED:
            return 'expired' if self.outcomes.get('expired') else None
        if not self.each:
            return task.outcome
        tasks = list(self.tasks(run, token))
        open_count = sum(1 for item in tasks if item.is_open)
        counts = {}
        for item in tasks:
            if item.state == Task.COMPLETED:
                counts[item.outcome] = counts.get(item.outcome, 0) + 1
        needed = self.needed(len(tasks))
        for outcome in self.choices():
            if counts.get(outcome, 0) >= needed:
                return outcome
        if all(counts.get(outcome, 0) + open_count < needed
               for outcome in self.choices()):
            return self.choices()[-1]
        return None

    def task_done(self, run, token, task):
        outcome = self.decide(run, token, task)
        if outcome is None:
            return
        if task.state == Task.COMPLETED and task.data:
            run.instance.variables.update(task.data)
        run.instance.variables['%s_outcome' % self.id] = outcome
        target = self.outcomes.get(outcome) or self.next
        if target is None:
            raise FlowError('%s: outcome %r leads nowhere' % (self.id, outcome))
        run.move(token, target, kind='task',
                 data={'outcome': outcome, 'task': task.pk})

    def leave(self, run, token):
        for task in self.tasks(run, token).filter(state__in=Task.OPEN):
            task.cancel()


#: ``type`` of the JSON form -> class.
TYPES = {cls.type: cls for cls in (State, Switch, ActionActivity, Wait, Parallel,
                                   Join, Subflow, HumanTask)}
