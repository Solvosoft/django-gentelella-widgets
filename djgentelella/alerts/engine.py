"""Firing, repeating and resolving alerts, and running the evaluators."""

import logging
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.db.models import Model
from django.utils import timezone

from .channels import get_channels
from .models import AbstractAlertEvent
from .registry import get_process, get_rule_model
from .triggers import OVERDUE, due_status

logger = logging.getLogger(__name__)


def _users(rule, obj, context, recipients):
    if recipients is None:
        users = rule.get_recipients(obj=obj, context=context)
    elif callable(recipients):
        users = recipients(rule, obj)
    else:
        users = recipients
    unique = {}
    for user in users or ():
        if user is not None:
            unique.setdefault(user.pk, user)
    return list(unique.values())


def _channels(rule):
    process = get_process(rule.process)
    return get_channels(process.channels if process else None)


def _dispatch(event, users, context):
    context = {**(context or {}), 'message': event.message, 'link': event.link,
               'rule': event.rule, 'event': event, 'object': event.content_object}
    for channel in _channels(event.rule):
        if not channel.applies(event):
            continue
        try:
            channel.send(event, users, context)
        except Exception:
            # One channel down (mail server, a bad template) must not keep
            # the others from notifying.
            logger.exception('Alert channel %s failed on event %s',
                             channel.name, event.pk)
    event.recipients = [user.get_username() for user in users]
    event.last_notified_at = timezone.now()
    event.save(update_fields=['recipients', 'last_notified_at'])


def _object_filter(obj, prefix=''):
    return {prefix + 'content_type': ContentType.objects.get_for_model(obj),
            prefix + 'object_id': obj.pk}


def fire_alert(rule, message, obj=None, *, dedupe_key='', recipients=None,
               context=None, link='', renotify_after=None, level=None):
    """Record that ``rule`` fired and notify through its process's channels.

    :param obj: the object the alert is about (generic foreign key).
    :param dedupe_key: while an event of this rule with this key is open, no
        new one is created: the open one is returned, notified again only
        when ``renotify_after`` (a ``timedelta``) passed since its last notice.
    :param recipients: users, or ``callable(rule, obj)`` giving them; ``None``
        asks ``rule.get_recipients(obj=..., context=...)``.
    :param context: extra context for the channels (the email template).
    :param level: the event's level, when not the rule's.
    :return: the event, new or the open one.
    """
    event_model = rule.get_event_model()
    if dedupe_key:
        existing = event_model.objects.filter(
            rule=rule, dedupe_key=dedupe_key, resolved_at__isnull=True).first()
        if existing is not None:
            return _renotify(existing, rule, obj, context, recipients,
                             renotify_after)

    fields = {
        'rule': rule, 'message': str(message), 'level': level or rule.level,
        'link': link or '', 'dedupe_key': dedupe_key or '',
        **rule.get_event_kwargs(obj),
    }
    if obj is not None:
        fields.update(_object_filter(obj))
    try:
        with transaction.atomic():
            event = event_model.objects.create(**fields)
    except IntegrityError:
        if not dedupe_key:
            raise
        # Two evaluations raced for the same key: the other one created it.
        return event_model.objects.get(rule=rule, dedupe_key=dedupe_key,
                                       resolved_at__isnull=True)
    _dispatch(event, _users(rule, obj, context, recipients), context)
    return event


def _renotify(event, rule, obj, context, recipients, renotify_after):
    if not renotify_after:
        return event
    last = event.last_notified_at or event.creation_date
    if last <= timezone.now() - renotify_after:
        _dispatch(event, _users(rule, obj, context, recipients), context)
    return event


def fire_due_alert(rule, obj, next_due, message, *, today=None, link='',
                   recipients=None, context=None):
    """Fire ``rule`` (a ``due`` trigger) for ``obj`` if ``next_due`` is near.

    Uses the threshold's ``days_before``; while overdue, notifies again every
    ``overdue_repeat_days`` (0: never). One open event per object and due
    date: registering the activity moves the date, and resolving the old
    event (:func:`resolve_alert` with the evidence) closes it.

    :return: the event, or ``None`` when the date is not near.
    """
    status = due_status(next_due, today, rule.threshold_value('days_before'))
    if status is None:
        return None
    repeat = rule.threshold_value('overdue_repeat_days') or 0
    content_type = ContentType.objects.get_for_model(obj)
    key = '%s:%s:%s' % (content_type.pk, obj.pk, next_due.isoformat())
    context = {**(context or {}), 'status': status, 'next_due': next_due}
    return fire_alert(
        rule, message, obj, dedupe_key=key, recipients=recipients,
        context=context, link=link,
        renotify_after=timedelta(days=repeat) if status == OVERDUE and repeat
        else None)


def resolve_alert(target=None, *, rule=None, dedupe_key=None, resolution=None,
                  user=None, event_model=None):
    """Close the open events of ``target`` and tell the channels.

    ``target`` is an event, or the object the events are about (all its open
    events, of ``rule`` if given). Without ``target``, ``rule`` and
    ``dedupe_key`` name the event. ``resolution`` is the evidence (the
    calibration done...), ``user`` who closed it.

    :return: the events closed.
    """
    if isinstance(target, AbstractAlertEvent):
        events = [target] if target.resolved_at is None else []
    else:
        if event_model is None:
            event_model = (rule or get_rule_model()).get_event_model()
        queryset = event_model.objects.filter(resolved_at__isnull=True)
        if rule is not None:
            queryset = queryset.filter(rule=rule)
        if isinstance(target, Model):
            queryset = queryset.filter(**_object_filter(target))
        elif dedupe_key and rule is not None:
            queryset = queryset.filter(dedupe_key=dedupe_key)
        else:
            raise ValueError('resolve_alert() needs an event, an object, or '
                             'rule and dedupe_key.')
        events = list(queryset.select_related('rule'))

    now = timezone.now()
    authenticated = user is not None and user.is_authenticated
    for event in events:
        event.resolved_at = now
        event.resolved_by = user if authenticated else None
        event.resolution = resolution
        event.save(update_fields=['resolved_at', 'resolved_by',
                                  'resolution_content_type',
                                  'resolution_object_id'])
        for channel in _channels(event.rule):
            if not channel.applies(event):
                continue
            try:
                channel.on_resolve(event, resolution=resolution, user=user)
            except Exception:
                logger.exception('Alert channel %s failed resolving event %s',
                                 channel.name, event.pk)
    return events


def run_alert_rules(process_code, **kwargs):
    """Evaluate every active rule of the process; ``kwargs`` go to the
    evaluator. A rule that raises is logged and does not stop the others.

    :return: how many rules were evaluated.
    """
    process = get_process(process_code)
    if process is None:
        return 0
    evaluator = process.evaluator
    rules = process.rule_model.objects.filter(process=process_code,
                                              is_active=True)
    total = 0
    for rule in rules:
        try:
            evaluator(rule, **kwargs)
        except Exception:
            logger.exception('Alert rule %s (%s) failed', rule.pk, process_code)
        total += 1
    return total
