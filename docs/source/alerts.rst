Alerts
=========

``djgentelella.alerts`` is the core of configurable alerts: an app says
*what* it watches and how to evaluate it, the project keeps *rules* (which
trigger, which threshold, how loud), and when a rule fires an *event* is
recorded and sent through *channels* (email, the notification bell, or your
own). An event stays open until it is resolved, preferably with the evidence
that closed it: the calibration done, the reading taken.

It is a plain module, not an app: it ships abstract models only, so nothing
goes in ``INSTALLED_APPS`` and no migration comes with it.

Models
--------

Make the two models concrete in one of your apps and point the setting at
the rule:

.. code:: python

    from djgentelella.alerts.models import AbstractAlertEvent, AbstractAlertRule

    class AlertRule(AbstractAlertRule):
        notify_users = models.ManyToManyField(User, blank=True)

        def get_recipients(self, obj=None, context=None):
            return list(self.notify_users.all())

    class AlertEvent(AbstractAlertEvent):
        rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE,
                                 related_name='events')

        class Meta(AbstractAlertEvent.Meta):
            pass

.. code:: python

    # settings.py
    GT_ALERTS_RULE_MODEL = 'myapp.AlertRule'

The event model is found from the rule: the model whose ``rule`` foreign key
points to it. Keep ``Meta(AbstractAlertEvent.Meta)``: its constraint makes
``dedupe_key`` unique among the *open* events of a rule.

``AbstractAlertRule`` has ``name``, ``process``, ``trigger`` (a trigger code),
``threshold`` (JSON), ``level`` (``info``, ``medium``, ``critical``),
``notification_code`` (an async_notification template; empty uses the
process's), ``is_active`` and ``created_by``. Two methods are hooks:

``get_recipients(obj=None, context=None)``
    The users to notify. By default only who created the rule: override it
    with your groups, roles or organizations.
``get_event_kwargs(obj=None)``
    Extra fields for the event, e.g. ``{'organization': self.organization}``.

``AbstractAlertEvent`` has the watched object as a generic foreign key
(``content_object``), ``message``, ``level``, ``link``, ``recipients`` (the
usernames notified), ``creation_date``, ``dedupe_key``, ``last_notified_at``
and the resolution: ``resolved_at``, ``resolved_by`` and ``resolution``,
another generic foreign key to the evidence.

Because they are generic relations, a watched model lists its alerts with
a ``GenericRelation``:

.. code:: python

    from django.contrib.contenttypes.fields import GenericRelation

    class Equipment(models.Model):
        alerts = GenericRelation(AlertEvent, related_query_name='equipment')

    equipment.alerts.filter(resolved_at__isnull=True)
    AlertEvent.objects.filter(equipment__lab=lab)

``object_id`` and ``resolution_object_id`` are integers. If your models use
UUID or text primary keys, redefine both as ``CharField(max_length=255)`` in
the concrete event.

Processes
-----------

An app registers its process from ``AppConfig.ready()``:

.. code:: python

    from djgentelella.alerts import TRIGGER_DUE, register_alert_process

    class LabConfig(AppConfig):
        def ready(self):
            register_alert_process(
                'lab.equipment_due', label=_('Equipment due activities'),
                evaluator='lab.alerts.evaluate_rule',
                triggers=[TRIGGER_DUE],
                permission='lab.change_equipment',
                notification_code='equipment-activity-due',
            )

``evaluator`` (a callable or its dotted path) receives each active rule of the
process. ``permission`` is who may manage its rules: ``processes_for(user)``
gives the processes a user may configure, for the form that edits rules.
``channels`` lists the channel names it notifies through (default: all).
``rule_model`` overrides the setting for this process.

``run_alert_rules('lab.equipment_due', **kwargs)`` evaluates every active rule
of the process, passing ``kwargs`` to the evaluator; a rule that raises is
logged and the others go on. Run it from cron, or with Celery from
``djgentelella.alerts.tasks.run_alert_rules_task`` (add
``app.autodiscover_tasks(['djgentelella.alerts'])``; it is not an app, so
Celery does not find it on its own).

Triggers
----------

A trigger is the kind of condition and the fields of its threshold. Four come
registered:

=============  ========================================================
``absolute``   ``value``: the maximum value.
``percent``    ``percent``: percentage over the average.
``missing``    ``periods``: periods without records.
``due``        ``days_before`` and ``overdue_repeat_days`` (0: never).
=============  ========================================================

Register your own with
``register_trigger(code, label, {field: ThresholdField(label, type, required,
min_value, default)})`` (a tuple of those arguments works too).
``validate_threshold(code, data)`` returns the threshold cleaned for storage
or raises a ``ValidationError`` per field; ``rule.threshold_value(name)``
reads a field back with its type; ``trigger_choices(codes)`` feeds a form.
``rule.full_clean()`` checks the process, the trigger and the threshold.

Firing
--------

.. code:: python

    from djgentelella.alerts import fire_alert

    def evaluate_rule(rule, **kwargs):
        limit = rule.threshold_value('value')
        for reading in readings_over(limit):
            fire_alert(rule, _('%s is over %s') % (reading, limit), reading.meter,
                       dedupe_key='reading:%d' % reading.pk,
                       link=reading.get_absolute_url())

``fire_alert(rule, message, obj=None, *, dedupe_key='', recipients=None,
context=None, link='', renotify_after=None, level=None)`` records the event and
notifies. While an event of the rule with that ``dedupe_key`` is open, no new
one is created and the open one is returned: evaluating every day does not
flood anyone. With ``renotify_after`` (a ``timedelta``) the open event is
notified again once that time passed since its last notice. ``recipients``
replaces ``rule.get_recipients()``: a list of users or ``callable(rule,
obj)``.

For due dates there is a helper that does all of that:

.. code:: python

    from djgentelella.alerts import fire_due_alert

    def evaluate_rule(rule, today=None):
        for plan in ActivityPlan.objects.filter(is_active=True):
            fire_due_alert(rule, plan.equipment, plan.next_due,
                           _('%s: calibration due') % plan.equipment,
                           today=today, link=plan.get_absolute_url())

It fires when ``next_due`` is within the threshold's ``days_before`` (status
``upcoming``), today (``due``) or past (``overdue``, repeated every
``overdue_repeat_days``). The status and the date reach the channels'
context. There is one event per object and due date; ``due_status(next_due,
today, days_before)`` is available on its own.

Resolving
-----------

.. code:: python

    from djgentelella.alerts import resolve_alert

    calibration = Calibration.objects.create(equipment=equipment, ...)
    resolve_alert(equipment, resolution=calibration, user=request.user)

``resolve_alert(target=None, *, rule=None, dedupe_key=None, resolution=None,
user=None)`` closes the open events of ``target``: an event, or the object the
events are about (all its open events, or those of ``rule``). Without a target,
``rule`` and ``dedupe_key`` name the event. It returns the events closed and
calls ``on_resolve`` on each channel. Registering the activity usually moves
the due date, so the next evaluation fires a new event for the new date.

Channels
----------

=================  ===========================================================
``email``          ``EmailChannel``: the async_notification template of the
                   rule (or its process) to the recipients with an email.
                   ``EmailChannel(sender=callable(event, code, emails,
                   context))`` sends through your own function.
``notification``   ``NotificationChannel``: the notification bell.
                   ``NotificationChannel(levels=['critical'])`` limits it.
=================  ===========================================================

A channel subclasses ``AlertChannel``, sets ``name`` and implements
``send(event, users, context)``; optionally ``applies(event)`` and
``on_resolve(event, resolution=None, user=None)``. ``register_channel()``
adds it or replaces the one with that name:

.. code:: python

    from djgentelella.alerts import AlertChannel, EmailChannel, register_channel

    class PendingTaskChannel(AlertChannel):
        name = 'pending_task'

        def send(self, event, users, context):
            for user in users:
                PendingTask.objects.create(user=user, alert=event, ...)

        def on_resolve(self, event, resolution=None, user=None):
            PendingTask.objects.filter(alert=event).update(state='finished')

    register_channel(PendingTaskChannel())
    register_channel(EmailChannel(sender=send_with_organization_template))

A channel that raises is logged and does not stop the others. The context a
channel gets is the ``context`` given to ``fire_alert`` plus ``message``,
``link``, ``rule``, ``event`` and ``object``.
