"""Triggers: the kinds of condition a rule watches, and their thresholds.

A trigger names what makes an evaluator fire (a value over a limit, a date
coming due...) and the fields of its threshold. Rules store the trigger's
``code`` and the threshold as JSON; :func:`validate_threshold` checks a
threshold against its fields and :func:`threshold_value` reads one back with
its type.

Four triggers come registered: ``absolute``, ``percent``, ``missing`` and
``due``. A project adds its own with :func:`register_trigger`.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

TRIGGER_ABSOLUTE = 'absolute'
TRIGGER_PERCENT = 'percent'
TRIGGER_MISSING = 'missing'
TRIGGER_DUE = 'due'

UPCOMING = 'upcoming'
DUE = 'due'
OVERDUE = 'overdue'

TRIGGERS = {}


class ThresholdField:
    """One field of a threshold: its label, its type and its bounds.

    ``type`` is ``int``, ``float`` or ``Decimal`` (stored as text, JSON has no
    decimals). A field that is not ``required`` takes ``default`` when absent.
    """

    def __init__(self, label, type=Decimal, required=True, min_value=None,
                 default=None):
        self.label = label
        self.type = type
        self.required = required
        self.min_value = min_value
        self.default = default

    def to_python(self, raw):
        try:
            value = self.type(str(raw).strip())
        except (TypeError, ValueError, InvalidOperation):
            raise ValidationError(_('Enter a number.'), code='invalid')
        if self.min_value is not None and value < self.min_value:
            raise ValidationError(
                _('Ensure this value is greater than or equal to %(min)s.'),
                code='min_value', params={'min': self.min_value})
        return value

    def to_json(self, value):
        return str(value) if isinstance(value, Decimal) else value


class Trigger:
    def __init__(self, code, label, threshold_fields):
        self.code = code
        self.label = label
        self.threshold_fields = {
            name: field if isinstance(field, ThresholdField)
            else ThresholdField(*field)
            for name, field in (threshold_fields or {}).items()
        }

    def __repr__(self):
        return '<Trigger %s>' % self.code


def register_trigger(code, label, threshold_fields=None):
    """Register (or replace) a trigger.

    ``threshold_fields`` maps each field name to a :class:`ThresholdField` or
    to the tuple of its arguments, ``(label, type, required, min_value,
    default)``.
    """
    trigger = Trigger(code, label, threshold_fields)
    TRIGGERS[code] = trigger
    return trigger


def get_trigger(code):
    try:
        return TRIGGERS[code]
    except KeyError:
        raise ValidationError(_('Unknown trigger.'), code='unknown_trigger')


def trigger_choices(codes=None):
    """``(code, label)`` pairs, for a form; ``codes`` limits them."""
    return [(code, trigger.label) for code, trigger in TRIGGERS.items()
            if codes is None or code in codes]


def validate_threshold(trigger_code, data):
    """The threshold ``data`` cleaned for storage, or ``ValidationError``.

    The error is a dict of field name to message. Unknown keys are dropped.
    """
    trigger = get_trigger(trigger_code)
    data = data or {}
    cleaned, errors = {}, {}
    for name, field in trigger.threshold_fields.items():
        raw = data.get(name)
        if raw is None or str(raw).strip() == '':
            if field.required:
                errors[name] = ValidationError(_('This field is required.'),
                                               code='required')
            elif field.default is not None:
                cleaned[name] = field.to_json(field.default)
            continue
        try:
            cleaned[name] = field.to_json(field.to_python(raw))
        except ValidationError as error:
            errors[name] = error
    if errors:
        raise ValidationError(errors)
    return cleaned


def threshold_value(trigger_code, threshold, name=None):
    """A field of a stored threshold, back in its type.

    ``name`` may be left out when the trigger has a single field. A field that
    is missing gives its default.
    """
    trigger = get_trigger(trigger_code)
    if name is None:
        if len(trigger.threshold_fields) != 1:
            raise ValueError('%s has several threshold fields: name one.'
                             % trigger_code)
        name = next(iter(trigger.threshold_fields))
    field = trigger.threshold_fields[name]
    raw = (threshold or {}).get(name)
    if raw is None:
        return field.default
    return field.type(str(raw))


def due_status(next_due, today=None, days_before=0):
    """Where ``next_due`` stands: ``'upcoming'`` within ``days_before`` days,
    ``'due'`` today, ``'overdue'`` past it, ``None`` otherwise or without a date.
    """
    if next_due is None:
        return None
    if isinstance(next_due, datetime):
        next_due = timezone.localdate(next_due) if timezone.is_aware(next_due) \
            else next_due.date()
    today = today or timezone.localdate()
    if isinstance(today, datetime):
        today = today.date()
    if not isinstance(next_due, date):
        raise TypeError('next_due must be a date')
    if next_due < today:
        return OVERDUE
    if next_due == today:
        return DUE
    if (next_due - today).days <= (days_before or 0):
        return UPCOMING
    return None


register_trigger(TRIGGER_ABSOLUTE, _('Absolute threshold'), {
    'value': ThresholdField(_('Maximum value'), Decimal),
})
register_trigger(TRIGGER_PERCENT, _('Percentage variation'), {
    'percent': ThresholdField(_('Percentage over the average'), Decimal,
                              min_value=Decimal('0.01')),
})
register_trigger(TRIGGER_MISSING, _('No records'), {
    'periods': ThresholdField(_('Periods without records'), int, min_value=1),
})
register_trigger(TRIGGER_DUE, _('Due date'), {
    'days_before': ThresholdField(_('Days before the due date'), int,
                                  min_value=0),
    'overdue_repeat_days': ThresholdField(
        _('Repeat every (days) while overdue, 0 never'), int, required=False,
        min_value=0, default=0),
})
