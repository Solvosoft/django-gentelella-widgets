"""Human tasks: the work a person does for a flow, or on its own.

:func:`create_task` makes one; the :class:`~djgentelella.flows.models.Task`
methods move it -- ``claim``, ``release``, ``delegate``, ``request_info``,
``submit_info``, ``complete`` -- each checked on a locked row and written to
its ``TaskHistory``. ``Task.objects.inbox(user)`` is what the user can see or
take. A task that belongs to a flow instance moves the flow when it is
completed (see the ``human_task`` activity).

The Celery task for the timers lives here too, where Celery's autodiscovery
looks for it; without Celery, run ``process_flow_timers`` from cron.
"""

from datetime import timedelta

from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from djgentelella.flows import signals
from djgentelella.flows.models import Task, TaskHistory
from djgentelella.flows.utils import json_safe


def _groups(groups):
    found = []
    for group in groups or ():
        if isinstance(group, Group):
            found.append(group)
        else:
            found.append(Group.objects.get_or_create(name=group)[0])
    return found


def create_task(*, obj, title, potential_owners=(), groups=(), due=None, priority=3,
                instance=None, outcome_choices=('approve', 'reject'), data=None,
                description='', activity='', token=None, on_expire=None,
                user=None):
    """Create a task on ``obj`` for ``potential_owners`` (users) and the
    members of ``groups`` (``Group`` objects or names).

    ``due`` is a datetime or a ``timedelta`` from now; ``priority`` goes from
    1 (urgent) to 5. With ``instance`` (and the ``activity`` and ``token``
    waiting for it) completing the task moves that flow; without it, the task
    stands alone. ``on_expire`` is what happens past ``due``
    (:meth:`Task.expire <djgentelella.flows.models.Task.expire>`). Sends
    ``task_created``.
    """
    if isinstance(due, timedelta):
        due = timezone.now() + due
    task = Task.objects.create(
        instance=instance, activity=activity, token=token,
        content_type=ContentType.objects.get_for_model(obj) if obj is not None
        else None,
        object_id=str(obj.pk) if obj is not None else '',
        title=str(title)[:255], description=description, priority=priority, due=due,
        outcome_choices=list(outcome_choices or ()), data=json_safe(data or {}),
        on_expire=json_safe(on_expire or {}))
    task.potential_owners.set(potential_owners)
    task.groups.set(_groups(groups))
    TaskHistory.objects.create(
        task=task, action='create', target=task.state,
        user=user if user is not None and user.is_authenticated else None)
    signals.task_created.send(sender=Task, task=task, user=user)
    return task


try:
    from celery import shared_task

    @shared_task
    def process_flow_timers_task():
        # Circular at module level: the timers import the engine, which
        # imports this module for create_task.
        from djgentelella.flows.timers import process_due  # noqa: PLC0415
        return process_due()

except ImportError:
    pass
