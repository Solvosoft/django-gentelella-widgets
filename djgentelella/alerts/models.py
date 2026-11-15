"""Abstract models of the alerts: a project makes them concrete.

::

    class AlertRule(AbstractAlertRule):
        organization = models.ForeignKey(Organization, on_delete=models.CASCADE)

        def get_recipients(self, obj=None, context=None):
            return users_of(self.organization)

    class AlertEvent(AbstractAlertEvent):
        rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE,
                                 related_name='events')

        class Meta(AbstractAlertEvent.Meta):
            pass

and ``GT_ALERTS_RULE_MODEL = 'myapp.AlertRule'``. The event model is found
from the rule: the model whose ``rule`` foreign key points to it.

Keep ``Meta(AbstractAlertEvent.Meta)``: its constraint is what makes
``dedupe_key`` unique among the open events of a rule.

Both carry a generic foreign key to the watched object (``content_object``)
and the event another one to the evidence that resolved it (``resolution``),
so a model can list its alerts with
``GenericRelation(AlertEvent, related_query_name=...)``. ``object_id`` is an
integer; a project whose models have UUID or text keys redefines it (and
``resolution_object_id``) as a ``CharField``.
"""

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from djgentelella.settings import USER_MODEL_BASE

from .registry import get_process
from .triggers import threshold_value, validate_threshold

INFO = 'info'
MEDIUM = 'medium'
CRITICAL = 'critical'
LEVELS = (
    (INFO, _('Informative')),
    (MEDIUM, _('Medium')),
    (CRITICAL, _('Critical')),
)


class AbstractAlertRule(models.Model):
    """What to watch (``process``), when to fire (``trigger`` and its
    ``threshold``) and how loud (``level``)."""

    INFO, MEDIUM, CRITICAL, LEVELS = INFO, MEDIUM, CRITICAL, LEVELS

    name = models.CharField(max_length=255, verbose_name=_('Name'))
    process = models.CharField(max_length=150, db_index=True,
                               verbose_name=_('Process'))
    trigger = models.CharField(max_length=100, verbose_name=_('Trigger'))
    threshold = models.JSONField(default=dict, blank=True,
                                 verbose_name=_('Threshold'))
    level = models.CharField(max_length=20, choices=LEVELS, default=MEDIUM,
                             verbose_name=_('Level'))
    notification_code = models.SlugField(
        max_length=150, blank=True, default='', verbose_name=_('Email template'),
        help_text=_('Empty uses the template of the process.'))
    is_active = models.BooleanField(default=True, verbose_name=_('Is active'))
    created_by = models.ForeignKey(
        USER_MODEL_BASE, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name=_('Created by'))

    class Meta:
        abstract = True
        ordering = ['process', 'name']
        verbose_name = _('Alert rule')
        verbose_name_plural = _('Alert rules')

    def __str__(self):
        return self.name

    # -- hooks ----------------------------------------------------------------
    def get_recipients(self, obj=None, context=None):
        """The users to notify about ``obj``. Override it: by default only
        whoever created the rule."""
        return [self.created_by] if self.created_by_id else []

    def get_event_kwargs(self, obj=None):
        """Extra fields of the event model, e.g. ``{'organization': ...}``."""
        return {}

    # -- helpers --------------------------------------------------------------
    @property
    def alert_process(self):
        return get_process(self.process)

    def get_notification_code(self):
        if self.notification_code:
            return self.notification_code
        process = self.alert_process
        return process.notification_code if process else ''

    def threshold_value(self, name=None):
        return threshold_value(self.trigger, self.threshold, name)

    @classmethod
    def get_event_model(cls):
        for relation in cls._meta.related_objects:
            model = relation.related_model
            if (issubclass(model, AbstractAlertEvent)
                    and relation.field.name == 'rule'):
                return model
        raise LookupError('No alert event model has a "rule" foreign key to %s.'
                          % cls._meta.label)

    def clean(self):
        super().clean()
        process = self.alert_process
        if process is None:
            raise ValidationError({'process': _('Unknown process.')})
        if self.trigger not in process.triggers:
            raise ValidationError(
                {'trigger': _('This process does not use that trigger.')})
        try:
            self.threshold = validate_threshold(self.trigger, self.threshold)
        except ValidationError as error:
            raise ValidationError({'threshold': error.messages})


class AbstractAlertEvent(models.Model):
    """One firing of a rule: about what, to whom, and how it was closed.

    The concrete model declares ``rule``, a foreign key to the rule model.
    """

    content_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+')
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    message = models.TextField(verbose_name=_('Message'))
    level = models.CharField(max_length=20, choices=LEVELS,
                             verbose_name=_('Level'))
    link = models.CharField(max_length=500, blank=True, default='',
                            verbose_name=_('Link'))
    recipients = models.JSONField(default=list, blank=True,
                                  verbose_name=_('Recipients'))
    creation_date = models.DateTimeField(auto_now_add=True,
                                         verbose_name=_('Date'))
    #: Same rule and key while open: one event, not one per evaluation.
    dedupe_key = models.CharField(max_length=255, blank=True, default='',
                                  db_index=True)
    last_notified_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True, db_index=True,
                                       verbose_name=_('Resolved at'))
    resolved_by = models.ForeignKey(
        USER_MODEL_BASE, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name=_('Resolved by'))
    resolution_content_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+')
    resolution_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    resolution = GenericForeignKey('resolution_content_type',
                                   'resolution_object_id')

    class Meta:
        abstract = True
        ordering = ['-creation_date']
        verbose_name = _('Alert event')
        verbose_name_plural = _('Alert events')
        constraints = [
            models.UniqueConstraint(
                fields=['rule', 'dedupe_key'],
                condition=Q(resolved_at__isnull=True) & ~Q(dedupe_key=''),
                name='%(app_label)s_%(class)s_open_dedupe'),
        ]

    def __str__(self):
        return self.message

    @property
    def is_open(self):
        return self.resolved_at is None
