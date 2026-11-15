"""Alert processes: who registers what, and which rule model holds the rules.

An app registers its process from ``AppConfig.ready()``::

    register_alert_process(
        'lab.equipment_due', label=_('Equipment due activities'),
        evaluator='lab.alerts.evaluate_rule',
        triggers=[TRIGGER_DUE],
        permission='lab.change_equipment',
        notification_code='equipment-activity-due',
    )

The evaluator is called with each active rule of the process (and the
keyword arguments of :func:`~djgentelella.alerts.engine.run_alert_rules`);
it calls :func:`~djgentelella.alerts.engine.fire_alert` when it has to.
"""

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

ALERT_PROCESSES = {}


class AlertProcess:
    def __init__(self, code, label, evaluator, triggers, permission=None,
                 notification_code='', channels=None, rule_model=None):
        self.code = code
        self.label = label
        self._evaluator = evaluator
        self.triggers = tuple(triggers)
        self.permission = permission
        self.notification_code = notification_code
        #: Channel names, or ``None`` for every registered channel.
        self.channels = tuple(channels) if channels is not None else None
        self._rule_model = rule_model

    @property
    def evaluator(self):
        if isinstance(self._evaluator, str):
            return import_string(self._evaluator)
        return self._evaluator

    @property
    def rule_model(self):
        return get_rule_model(self._rule_model)

    def __repr__(self):
        return '<AlertProcess %s>' % self.code


def register_alert_process(code, label, evaluator, triggers, permission=None,
                           notification_code='', channels=None, rule_model=None):
    """Register (or replace) the process ``code``.

    :param evaluator: callable ``(rule, **kwargs)`` or its dotted path.
    :param triggers: trigger codes its rules may use.
    :param permission: who may manage its rules (see :func:`processes_for`).
    :param notification_code: async_notification template of its emails,
        when the rule has none.
    :param channels: names of the channels it notifies through; ``None`` is
        every registered channel.
    :param rule_model: model (or ``'app.Model'``) of its rules; defaults to
        ``settings.GT_ALERTS_RULE_MODEL``.
    """
    process = AlertProcess(code, label, evaluator, triggers, permission,
                           notification_code, channels, rule_model)
    ALERT_PROCESSES[code] = process
    return process


def get_process(code):
    return ALERT_PROCESSES.get(code)


def processes_for(user):
    """The processes whose rules ``user`` may manage."""
    if user is None or not user.is_authenticated:
        return {}
    return {code: process for code, process in ALERT_PROCESSES.items()
            if not process.permission or user.has_perm(process.permission)}


def get_rule_model(model=None):
    """The rule model: ``model`` (class or ``'app.Model'``) or the setting."""
    model = model or getattr(settings, 'GT_ALERTS_RULE_MODEL', None)
    if model is None:
        raise ImproperlyConfigured(
            'Set GT_ALERTS_RULE_MODEL or pass rule_model to '
            'register_alert_process().')
    if isinstance(model, str):
        return apps.get_model(model)
    return model
