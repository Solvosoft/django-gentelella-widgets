"""Everything a flow waits for by the clock, for ``process_flow_timers`` and
the Celery task: the deadlines of states, the ``wait`` activities and the
tasks past their ``due``."""

import logging

from django.utils import timezone

from djgentelella.flows.base import LIVE, flow_for_instance
from djgentelella.flows.models import FlowInstance, Task

logger = logging.getLogger(__name__)


def due_instances(now=None):
    """``[(flow, instance pk), ...]`` with a timer past due."""
    now = now or timezone.now()
    found = []
    for instance in FlowInstance.objects.filter(
            due_at__lte=now, status__in=LIVE).order_by('due_at'):
        try:
            found.append((flow_for_instance(instance), instance.pk))
        except Exception:
            logger.exception('Flow instance %s (%s) has no flow', instance.pk,
                             instance.flow)
    return found


def due_tasks(now=None):
    now = now or timezone.now()
    return Task.objects.filter(state__in=Task.OPEN, due__lte=now).order_by('due')


def process_due(now=None):
    """Run every timer past due; ``{result: count}``. One that fails is
    logged and leaves the others running.

    Results: ``moved``, ``reminded``, ``cleared`` (instances), and
    ``task_completed``, ``task_escalated``, ``task_notified``,
    ``task_expired`` (tasks).
    """
    now = now or timezone.now()
    counts = {}
    for flow, pk in due_instances(now):
        try:
            result = flow.run_deadline(pk, now) or 'skipped'
        except Exception:
            logger.exception('Timer of flow instance %s (%s) failed', pk, flow.name)
            result = 'failed'
        counts[result] = counts.get(result, 0) + 1
    for task in due_tasks(now):
        try:
            result = task.expire(now)
            result = 'task_%s' % result if result else 'skipped'
        except Exception:
            logger.exception('Expiring task %s failed', task.pk)
            result = 'task_failed'
        counts[result] = counts.get(result, 0) + 1
    return counts
