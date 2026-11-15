"""The flow engine's tables: definitions, instances and their log, and the
human tasks with their comments and history.

The engine itself is :mod:`djgentelella.flows.base`; this module imports
nothing of it, so models of other apps may point here.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.template import Context, Template
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from djgentelella.flows import signals
from djgentelella.flows.exceptions import TaskNotAllowed
from djgentelella.notification import create_notification
from djgentelella.settings import USER_MODEL_BASE


def _person(user):
    """``user``, or None for the system and for anonymous users."""
    return user if user is not None and user.is_authenticated else None


class FlowDefinition(models.Model):
    """A flow written as JSON (``flows/schema_v2.json``), loaded at runtime.

    It builds the same :class:`~djgentelella.flows.base.Flow` object as a
    class in ``gtflows.py``. Each publication is a new ``version``; an
    instance stays bound to the definition it started with, so publishing
    does not change the instances under way.
    """

    name = models.CharField(max_length=150, verbose_name=_('Name'))
    version = models.PositiveIntegerField(default=1, verbose_name=_('Version'))
    site = models.ForeignKey('sites.Site', null=True, blank=True,
                             on_delete=models.CASCADE, verbose_name=_('Site'))
    title = models.CharField(max_length=200, blank=True, default='',
                             verbose_name=_('Title'))
    document = models.JSONField(verbose_name=_('Document'))
    #: Only active definitions start new instances; the newest one wins.
    is_active = models.BooleanField(default=True, verbose_name=_('Active'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', '-version']
        verbose_name = _('Flow definition')
        verbose_name_plural = _('Flow definitions')
        constraints = [
            # A NULL site is "global"; NULLs never collide in a plain unique.
            models.UniqueConstraint(fields=['name', 'version', 'site'],
                                    condition=Q(site__isnull=False),
                                    name='gt_flowdef_site_unique'),
            models.UniqueConstraint(fields=['name', 'version'],
                                    condition=Q(site__isnull=True),
                                    name='gt_flowdef_global_unique'),
        ]

    def __str__(self):
        return '%s v%d' % (self.name, self.version)


class FlowInstance(models.Model):
    """Where one object stands in one flow.

    Kept apart from the object's own model, so a flow needs no field on it and
    one model can go through several flows. ``object_id`` is text so any
    primary key type fits.

    ``tokens`` are the activities under way: one in a plain state machine,
    several between a ``parallel`` and its ``join``. ``state`` is the one the
    pages show (and the inbox filters on): the token's activity, or the
    parallel the tokens came from.
    """

    RUNNING, SUSPENDED, ERROR = 'running', 'suspended', 'error'
    COMPLETED, TERMINATED = 'completed', 'terminated'
    STATUSES = [
        (RUNNING, _('Running')),
        (SUSPENDED, _('Suspended')),
        (ERROR, _('Error')),
        (COMPLETED, _('Completed')),
        (TERMINATED, _('Terminated')),
    ]

    flow = models.CharField(max_length=150, verbose_name=_('Flow'))
    version = models.PositiveIntegerField(default=1, verbose_name=_('Version'))
    #: The JSON definition it runs; empty for a flow declared in Python.
    definition = models.ForeignKey(FlowDefinition, null=True, blank=True,
                                   on_delete=models.PROTECT,
                                   related_name='instances')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=255)
    content_object = GenericForeignKey('content_type', 'object_id')
    state = models.CharField(max_length=100, verbose_name=_('State'))
    status = models.CharField(max_length=20, choices=STATUSES, default=RUNNING,
                              db_index=True, verbose_name=_('Status'))
    tokens = models.JSONField(default=list, blank=True)
    #: Last token id handed out; tasks and joins refer to tokens by id.
    token_seq = models.PositiveIntegerField(default=0)
    variables = models.JSONField(default=dict, blank=True,
                                 verbose_name=_('Variables'))
    error = models.TextField(blank=True, default='', verbose_name=_('Error'))
    assigned_to = models.ForeignKey(
        USER_MODEL_BASE, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='gt_flow_assignments', verbose_name=_('Assigned to'))
    assigned_group = models.ForeignKey(
        Group, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='gt_flow_assignments', verbose_name=_('Assigned group'))
    #: How many times the state changed.
    visit = models.PositiveIntegerField(default=0)
    entered_at = models.DateTimeField(null=True, blank=True,
                                      verbose_name=_('In this state since'))
    #: The earliest timer of its tokens: a deadline or a wait.
    due_at = models.DateTimeField(null=True, blank=True, db_index=True,
                                  verbose_name=_('Due'))
    #: The instance whose ``subflow`` activity started this one.
    parent = models.ForeignKey('self', null=True, blank=True,
                               on_delete=models.CASCADE, related_name='children')
    parent_token = models.PositiveIntegerField(null=True, blank=True)
    site = models.ForeignKey('sites.Site', null=True, blank=True,
                             on_delete=models.SET_NULL, verbose_name=_('Site'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _('Flow instance')
        verbose_name_plural = _('Flow instances')
        constraints = [
            models.UniqueConstraint(fields=['flow', 'content_type', 'object_id'],
                                    name='gt_flow_instance_unique'),
        ]
        indexes = [models.Index(fields=['flow', 'state'])]

    def __str__(self):
        return '%s: %s' % (self.flow, self.state)

    def active_tokens(self):
        return [token for token in self.tokens if token.get('status') == 'active']

    def object_exists(self):
        """Whether the object this instance is about still exists."""
        model = self.content_type.model_class()
        if model is None:  # the model itself went away
            return False
        try:
            pk = model._meta.pk.to_python(self.object_id)
        except (ValidationError, ValueError, TypeError):
            return False
        # _base_manager: a default manager that hides rows (soft delete,
        # archived, by Site) must not make a living object look deleted, as
        # the callers then forget the instance and its log.
        return model._base_manager.filter(pk=pk).exists()


class FlowTransitionLog(models.Model):
    """One event of an instance: a transition run (by hand, automatic or on a
    timer), an activity entered, a change of assignment, of variables or of
    the instance's status (suspend, resume, retry...)."""

    KINDS = [
        ('transition', _('Transition')),
        ('auto', _('Automatic')),
        ('timeout', _('Timer')),
        ('activity', _('Activity')),
        ('signal', _('Signal')),
        ('task', _('Task')),
        ('error', _('Error')),
        ('variables', _('Variables')),
        ('start', _('Start')),
        ('complete', _('Completed')),
        ('suspend', _('Suspend')),
        ('resume', _('Resume')),
        ('terminate', _('Terminate')),
        ('retry', _('Retry')),
        ('claim', _('Claim')),
        ('release', _('Release')),
        ('reassign', _('Reassign')),
    ]

    instance = models.ForeignKey(FlowInstance, on_delete=models.CASCADE,
                                 related_name='log')
    #: The transition or the activity.
    transition = models.CharField(max_length=100, verbose_name=_('Transition'))
    source = models.CharField(max_length=100, verbose_name=_('From'))
    target = models.CharField(max_length=100, verbose_name=_('To'))
    user = models.ForeignKey(USER_MODEL_BASE, null=True, blank=True,
                             on_delete=models.SET_NULL, verbose_name=_('User'))
    kind = models.CharField(max_length=20, choices=KINDS, default='transition',
                            verbose_name=_('Kind'))
    comment = models.TextField(blank=True, default='', verbose_name=_('Comment'))
    data = models.JSONField(default=dict, blank=True, verbose_name=_('Data'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        verbose_name = _('Flow event')
        verbose_name_plural = _('Flow events')

    def __str__(self):
        return '%s: %s -> %s' % (self.transition, self.source, self.target)


class TaskQuerySet(models.QuerySet):
    def open(self):
        return self.filter(state__in=Task.OPEN)

    def for_user(self, user):
        """Tasks ``user`` owns, may claim, or was asked information on."""
        if user is None or not user.is_authenticated:
            return self.none()
        return self.filter(
            Q(actual_owner=user) | Q(info_from=user)
            | Q(actual_owner__isnull=True, potential_owners=user)
            | Q(actual_owner__isnull=True, groups__in=user.groups.all())
        ).distinct()

    def inbox(self, user):
        """The open tasks ``user`` can see or take."""
        return self.open().for_user(user)


class Task(models.Model):
    """A piece of work for a person: an approval, a review, a form to fill.

    It may belong to a flow instance (a ``human_task`` activity waits for its
    outcome) or stand alone. See :mod:`djgentelella.flows.tasks`.
    """

    UNASSIGNED, ASSIGNED, INFO_REQUESTED = 'unassigned', 'assigned', 'info_requested'
    COMPLETED, CANCELLED, EXPIRED = 'completed', 'cancelled', 'expired'
    STATES = [
        (UNASSIGNED, _('Unassigned')),
        (ASSIGNED, _('Assigned')),
        (INFO_REQUESTED, _('Information requested')),
        (COMPLETED, _('Completed')),
        (CANCELLED, _('Cancelled')),
        (EXPIRED, _('Expired')),
    ]
    OPEN = (UNASSIGNED, ASSIGNED, INFO_REQUESTED)
    PRIORITIES = [(1, _('Urgent')), (2, _('High')), (3, _('Normal')),
                  (4, _('Low')), (5, _('Lowest'))]

    instance = models.ForeignKey(FlowInstance, null=True, blank=True,
                                 on_delete=models.CASCADE, related_name='tasks')
    #: The ``human_task`` activity and the token that wait for it.
    activity = models.CharField(max_length=100, blank=True, default='')
    token = models.PositiveIntegerField(null=True, blank=True)
    content_type = models.ForeignKey(ContentType, null=True, blank=True,
                                     on_delete=models.CASCADE)
    object_id = models.CharField(max_length=255, blank=True, default='')
    content_object = GenericForeignKey('content_type', 'object_id')
    title = models.CharField(max_length=255, verbose_name=_('Title'))
    description = models.TextField(blank=True, default='',
                                   verbose_name=_('Description'))
    potential_owners = models.ManyToManyField(
        USER_MODEL_BASE, blank=True, related_name='gt_potential_tasks',
        verbose_name=_('Potential owners'))
    groups = models.ManyToManyField(Group, blank=True, related_name='gt_tasks',
                                    verbose_name=_('Groups'))
    actual_owner = models.ForeignKey(
        USER_MODEL_BASE, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='gt_owned_tasks', verbose_name=_('Owner'))
    #: Who was asked for information, while ``info_requested``.
    info_from = models.ForeignKey(
        USER_MODEL_BASE, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='gt_info_tasks', verbose_name=_('Information from'))
    state = models.CharField(max_length=20, choices=STATES, default=UNASSIGNED,
                             db_index=True, verbose_name=_('State'))
    priority = models.PositiveSmallIntegerField(choices=PRIORITIES, default=3,
                                                verbose_name=_('Priority'))
    due = models.DateTimeField(null=True, blank=True, db_index=True,
                               verbose_name=_('Due'))
    #: What happens past ``due``: ``{"outcome": ...}``, ``{"escalate": {...}}``
    #: and/or ``{"notify": "..."}``; see :meth:`Task.expire`.
    on_expire = models.JSONField(default=dict, blank=True)
    outcome_choices = models.JSONField(default=list, blank=True)
    outcome = models.CharField(max_length=100, blank=True, default='',
                               verbose_name=_('Outcome'))
    data = models.JSONField(default=dict, blank=True, verbose_name=_('Data'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True,
                                        verbose_name=_('Completed'))

    objects = TaskQuerySet.as_manager()

    class Meta:
        ordering = ['priority', 'due', 'pk']
        verbose_name = _('Task')
        verbose_name_plural = _('Tasks')
        indexes = [models.Index(fields=['state', 'due'])]

    def __str__(self):
        return self.title

    @property
    def is_open(self):
        return self.state in self.OPEN

    @property
    def overdue(self):
        return bool(self.due and self.is_open and self.due <= timezone.now())

    # -- who may do what ----------------------------------------------------------
    def is_potential_owner(self, user):
        """Named in ``potential_owners``, or a member of one of ``groups``."""
        if user is None or not user.is_authenticated:
            return False
        if self.potential_owners.filter(pk=user.pk).exists():
            return True
        return self.groups.filter(pk__in=user.groups.values('pk')).exists()

    def can_view(self, user):
        if user is None or not user.is_authenticated:
            return False
        return (user.pk in (self.actual_owner_id, self.info_from_id)
                or self.is_potential_owner(user)
                or user.has_perm('gtflows.view_task'))

    def can(self, user, action):
        """Whether ``user`` may ``claim``, ``release``, ``delegate``,
        ``request_info``, ``submit_info``, ``complete`` or ``comment`` now."""
        if user is None or not user.is_authenticated:
            return False
        owner = self.actual_owner_id == user.pk
        if action == 'claim':
            return self.state == self.UNASSIGNED and self.is_potential_owner(user)
        if action in ('release', 'delegate', 'request_info'):
            return self.state == self.ASSIGNED and owner
        if action == 'submit_info':
            return self.state == self.INFO_REQUESTED and self.info_from_id == user.pk
        if action == 'complete':
            # A potential owner may complete an unclaimed task: it is claimed
            # and completed in one go.
            return (self.state == self.ASSIGNED and owner) or (
                self.state == self.UNASSIGNED and self.is_potential_owner(user))
        if action == 'comment':
            return self.is_open and self.can_view(user)
        return False

    def allowed_actions(self, user):
        return [action for action in ('claim', 'release', 'delegate', 'request_info',
                                      'submit_info', 'complete', 'comment')
                if self.can(user, action)]

    # -- changes ------------------------------------------------------------------
    def _change(self, user, action, apply, comment='', to_user=None, data=None,
                check=True, history=None):
        """Lock the row, check ``action`` again on the fresh copy, ``apply``
        it and write the history; refuse with :class:`TaskNotAllowed`.

        The lock is what keeps two users from both claiming or completing the
        same task: the second one waits, then finds it already taken.
        """
        with transaction.atomic():
            task = Task.objects.select_for_update().get(pk=self.pk)
            if check and not task.can(user, action):
                raise TaskNotAllowed(_('You cannot %(action)s this task now.') % {
                    'action': task.action_label(action)})
            source = task.state
            apply(task)
            task.save()
            TaskHistory.objects.create(
                task=task, action=history or action, user=_person(user),
                to_user=to_user, source=source, target=task.state,
                comment=comment, data=data or {})
            if comment:
                TaskComment.objects.create(task=task, user=_person(user), text=comment)
            self.refresh_from_db()
            return task

    @staticmethod
    def action_label(action):
        return str(dict(TaskHistory.ACTIONS).get(action, action)).lower()

    def claim(self, user, comment=''):
        def apply(task):
            task.actual_owner = user
            task.state = Task.ASSIGNED
        return self._change(user, 'claim', apply, comment)

    def release(self, user, comment=''):
        """Give the task back to its potential owners."""
        def apply(task):
            task.actual_owner = None
            task.state = Task.UNASSIGNED
        return self._change(user, 'release', apply, comment)

    def delegate(self, user, to_user, comment=''):
        """Hand the task to ``to_user``, who becomes its owner."""
        def apply(task):
            task.actual_owner = to_user
            task.potential_owners.add(to_user)
        return self._change(user, 'delegate', apply, comment, to_user=to_user)

    def request_info(self, user, to_user, comment):
        """Ask ``to_user`` something; the task waits for their answer."""
        def apply(task):
            task.info_from = to_user
            task.state = Task.INFO_REQUESTED
        return self._change(user, 'request_info', apply, comment, to_user=to_user)

    def submit_info(self, user, comment):
        """Answer a request for information; the task goes back to its owner."""
        def apply(task):
            task.info_from = None
            task.state = Task.ASSIGNED
        return self._change(user, 'submit_info', apply, comment,
                            to_user=self.actual_owner)

    def comment(self, user, text):
        if not self.can(user, 'comment'):
            raise TaskNotAllowed(_('You cannot comment on this task.'))
        return TaskComment.objects.create(task=self, user=user, text=text)

    def complete(self, user, outcome, comment='', data=None, check=True,
                 history='complete'):
        """Close the task with ``outcome`` (one of ``outcome_choices``) and, if
        it belongs to a flow, move the flow on -- in the same transaction.
        ``user=None`` is the system (a task past due), which no check stops.
        """
        if self.outcome_choices and outcome not in self.outcome_choices:
            raise TaskNotAllowed(_('%(outcome)s is not an outcome of this task.') % {
                'outcome': outcome})
        if self.instance_id is not None and self.is_open \
                and not self.instance.object_exists():
            # Deleted where no receiver saw it (see forget_object): clean up
            # now, and refuse instead of failing in the engine.
            forget_instances(FlowInstance.objects.filter(pk=self.instance_id))
            self.refresh_from_db()
            raise TaskNotAllowed(_('The object of this task no longer exists; the '
                                   'task was cancelled.'))

        def apply(task):
            if task.actual_owner_id is None and user is not None:
                task.actual_owner = user
            task.state = Task.COMPLETED
            task.outcome = outcome
            task.completed_at = timezone.now()
            task.data = {**task.data, **(data or {})}

        with transaction.atomic():
            task = self._change(user, 'complete', apply, comment, check=check,
                                data={'outcome': outcome}, history=history)
            signals.task_completed.send(sender=Task, task=task, user=user,
                                        outcome=outcome)
        return self

    def cancel(self, user=None, comment=''):
        """Closed without an outcome: by the flow (another branch won, the
        instance was terminated) or by hand."""
        def apply(task):
            task.state = Task.CANCELLED
            task.completed_at = timezone.now()
        return self._change(user, 'cancel', apply, comment, check=False)

    def expire(self, now=None):
        """What ``process_flow_timers`` does to a task past ``due``.

        ``on_expire`` decides it:

        * ``{"outcome": "reject"}`` completes it with that outcome, as the
          system;
        * ``{"escalate": {"users": [pk, ...], "groups": ["Name"],
          "priority": 1, "due": <seconds>}}`` hands it to them, unclaimed,
          with a new deadline when ``due`` is given;
        * ``{"notify": "text"}`` (alone or with ``escalate``) sends the
          owners -- the new ones, when escalated -- a notification.

        With none of them, the task becomes ``expired``; a flow waiting for it
        follows its ``expired`` outcome when it has one. A task whose flow
        object no longer exists is cancelled instead (``'cancelled'``).
        Returns what happened, or None when it was not due any more.
        """
        now = now or timezone.now()
        config = self.on_expire or {}
        if self.instance_id is not None and self.is_open \
                and not self.instance.object_exists():
            forget_instances(FlowInstance.objects.filter(pk=self.instance_id))
            self.refresh_from_db()
            return 'cancelled'
        with transaction.atomic():
            task = Task.objects.select_for_update().get(pk=self.pk)
            if not task.is_open or task.due is None or task.due > now:
                return None
            if config.get('outcome'):
                task.complete(None, config['outcome'], check=False, history='expire')
                result = 'completed'
            elif config.get('escalate'):
                escalate = config['escalate']

                def apply(task):
                    task.actual_owner = None
                    task.info_from = None
                    task.state = Task.UNASSIGNED
                    task.potential_owners.set(escalate.get('users', []))
                    task.groups.set(Group.objects.filter(
                        name__in=escalate.get('groups', [])))
                    task.priority = escalate.get('priority', task.priority)
                    seconds = escalate.get('due')
                    task.due = now + timedelta(seconds=seconds) if seconds else None
                task._change(None, 'escalate', apply, check=False, data=escalate)
                result = 'escalated'
            elif config.get('notify'):
                task._change(None, 'expire', lambda task: setattr(task, 'due', None),
                             check=False)
                result = 'notified'
            else:
                def apply(task):
                    task.state = Task.EXPIRED
                    task.completed_at = now
                task._change(None, 'expire', apply, check=False)
                signals.task_completed.send(sender=Task, task=task, user=None,
                                            outcome='expired')
                result = 'expired'
            if config.get('notify'):
                task.notify_owners(config['notify'])
            self.refresh_from_db()
            return result

    def owners(self):
        """Who the task is for now: its owner, or every potential owner."""
        User = get_user_model()
        if self.actual_owner_id:
            return [self.actual_owner]
        return list(User.objects.filter(
            Q(pk__in=self.potential_owners.values('pk'))
            | Q(groups__in=self.groups.all()), is_active=True).distinct())

    def notify_owners(self, message, message_type='warning'):
        message = Template(message).render(Context({'task': self,
                                                    'object': self.content_object}))
        for user in self.owners():
            create_notification(message, user, message_type,
                                link=self.get_absolute_url())

    def get_absolute_url(self):
        try:
            return reverse('task_detail', args=[self.pk])
        except NoReverseMatch:  # the project did not include djgentelella's URLs
            return '#'


class TaskComment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(USER_MODEL_BASE, null=True, blank=True,
                             on_delete=models.SET_NULL, verbose_name=_('User'))
    text = models.TextField(verbose_name=_('Comment'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']
        verbose_name = _('Task comment')
        verbose_name_plural = _('Task comments')

    def __str__(self):
        return self.text[:50]


class TaskHistory(models.Model):
    ACTIONS = [
        ('create', _('Created')),
        ('claim', _('Claimed')),
        ('release', _('Released')),
        ('delegate', _('Delegated')),
        ('request_info', _('Information requested')),
        ('submit_info', _('Information submitted')),
        ('complete', _('Completed')),
        ('cancel', _('Cancelled')),
        ('expire', _('Expired')),
        ('escalate', _('Escalated')),
    ]

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='history')
    action = models.CharField(max_length=20, choices=ACTIONS,
                              verbose_name=_('Action'))
    user = models.ForeignKey(USER_MODEL_BASE, null=True, blank=True,
                             on_delete=models.SET_NULL, related_name='+',
                             verbose_name=_('User'))
    to_user = models.ForeignKey(USER_MODEL_BASE, null=True, blank=True,
                                on_delete=models.SET_NULL, related_name='+',
                                verbose_name=_('To'))
    source = models.CharField(max_length=20, blank=True, default='')
    target = models.CharField(max_length=20, blank=True, default='')
    comment = models.TextField(blank=True, default='', verbose_name=_('Comment'))
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']
        verbose_name = _('Task history')
        verbose_name_plural = _('Task history')

    def __str__(self):
        return '%s: %s' % (self.task_id, self.action)


# -- objects that go away -------------------------------------------------------------

def object_key(model, pk):
    """How an object's primary key is stored in ``FlowInstance.object_id``:
    UUIDs as 32 hex digits, anything else as its text."""
    if isinstance(model._meta.pk, models.UUIDField) and pk is not None:
        return pk.hex if hasattr(pk, 'hex') else str(pk).replace('-', '')
    return str(pk)


def forget_instances(instances, comment=None):
    """Forget the flow instances ``instances`` (a queryset): their objects are
    gone.

    The open tasks of the instances -- and of the subflows they started, which
    go with them -- are cancelled, with an entry in their history, and every
    task of theirs is kept as a task of no flow, so the inbox and the history
    still show what happened. Then the instances (with their log and their
    subflows) are deleted, as before: the object's key is free again.
    """
    if comment is None:
        comment = str(_('The object of the flow was deleted.'))
    with transaction.atomic():
        top = set(instances.values_list('pk', flat=True))
        if not top:
            return 0
        found, frontier = set(top), set(top)
        while frontier:
            frontier = set(FlowInstance.objects.filter(parent__in=frontier)
                           .values_list('pk', flat=True)) - found
            found |= frontier
        tasks = Task.objects.filter(instance__in=found)
        for task in tasks.filter(state__in=Task.OPEN):
            task.cancel(None, comment)
        tasks.update(instance=None)
        FlowInstance.objects.filter(pk__in=top).delete()
    return len(top)


def forget_object(model, pk, comment=None):
    """The object ``pk`` of ``model`` was deleted: forget the instances of
    every flow it was in (:func:`forget_instances`). The engine calls it from
    ``post_delete``; call it yourself after deleting objects in a way that
    sends no signals (``QuerySet.update``, raw SQL)."""
    content_type = ContentType.objects.get_for_model(model)
    return forget_instances(FlowInstance.objects.filter(
        content_type=content_type, object_id=object_key(model, pk)), comment)
