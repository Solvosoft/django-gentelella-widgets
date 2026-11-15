"""Configurable alerts: rules a project evaluates and channels that notify.

An app registers a *process* (what it watches and how it evaluates it) with
:func:`register_alert_process`; the project keeps the *rules* (which trigger,
which threshold, how loud) in a concrete subclass of
:class:`~djgentelella.alerts.models.AbstractAlertRule`; the evaluator calls
:func:`fire_alert`, which records an event (once per ``dedupe_key`` while
open) and notifies through the channels; :func:`resolve_alert` closes it with
its evidence. See ``docs/source/alerts.rst``.

This is a plain module, not an app: it ships abstract models only, so it
needs nothing in ``INSTALLED_APPS`` and brings no migration.
"""

from .channels import (
    AlertChannel,
    EmailChannel,
    NotificationChannel,
    get_channels,
    register_channel,
    unregister_channel,
)
from .engine import fire_alert, fire_due_alert, resolve_alert, run_alert_rules
from .registry import (
    get_process,
    get_rule_model,
    processes_for,
    register_alert_process,
)
from .triggers import (
    DUE,
    OVERDUE,
    TRIGGER_ABSOLUTE,
    TRIGGER_DUE,
    TRIGGER_MISSING,
    TRIGGER_PERCENT,
    UPCOMING,
    ThresholdField,
    due_status,
    get_trigger,
    register_trigger,
    threshold_value,
    trigger_choices,
    validate_threshold,
)

__all__ = [
    'AlertChannel', 'EmailChannel', 'NotificationChannel', 'get_channels',
    'register_channel', 'unregister_channel',
    'fire_alert', 'fire_due_alert', 'resolve_alert', 'run_alert_rules',
    'get_process', 'get_rule_model', 'processes_for', 'register_alert_process',
    'DUE', 'OVERDUE', 'UPCOMING', 'TRIGGER_ABSOLUTE', 'TRIGGER_DUE',
    'TRIGGER_MISSING', 'TRIGGER_PERCENT', 'ThresholdField', 'due_status',
    'get_trigger', 'register_trigger', 'threshold_value', 'trigger_choices',
    'validate_threshold',
]
