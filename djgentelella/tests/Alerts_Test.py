"""djgentelella.alerts: triggers, processes, firing, dedupe, channels, resolve.

The concrete models are the demo's (``demoapp.AlertRule``/``AlertEvent``,
``GT_ALERTS_RULE_MODEL`` in the demo settings); the watched object is
``demoapp.Equipment`` and the evidence ``demoapp.Calibration``.
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import AnonymousUser, Permission, User
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from demoapp.models import AlertEvent, AlertRule, Calibration, Equipment
from djgentelella import alerts
from djgentelella.alerts import channels as channels_module
from djgentelella.alerts import registry
from djgentelella.models import Notification

TODAY = date(2026, 11, 15)
PROCESS = 'tests.equipment_due'


class RecordingChannel(alerts.AlertChannel):
    name = 'recording'

    def __init__(self):
        self.sent, self.resolved = [], []

    def send(self, event, users, context):
        self.sent.append((event, list(users), context))

    def on_resolve(self, event, resolution=None, user=None):
        self.resolved.append((event, resolution, user))


class BrokenChannel(alerts.AlertChannel):
    name = 'broken'

    def send(self, event, users, context):
        raise RuntimeError('down')

    def on_resolve(self, event, resolution=None, user=None):
        raise RuntimeError('down')


class TriggerTests(SimpleTestCase):

    def test_due_status(self):
        self.assertEqual(alerts.due_status(TODAY - timedelta(1), TODAY), 'overdue')
        self.assertEqual(alerts.due_status(TODAY, TODAY), 'due')
        self.assertEqual(alerts.due_status(TODAY + timedelta(30), TODAY, 30),
                         'upcoming')
        self.assertIsNone(alerts.due_status(TODAY + timedelta(31), TODAY, 30))
        self.assertIsNone(alerts.due_status(None, TODAY, 30))

    def test_validate_threshold_cleans_and_types(self):
        self.assertEqual(alerts.validate_threshold('percent', {'percent': ' 12.5 '}),
                         {'percent': '12.5'})
        self.assertEqual(alerts.validate_threshold('due', {'days_before': '30'}),
                         {'days_before': 30, 'overdue_repeat_days': 0})
        self.assertEqual(alerts.threshold_value('percent', {'percent': '12.5'}),
                         Decimal('12.5'))

    def test_validate_threshold_errors_by_field(self):
        with self.assertRaises(ValidationError) as caught:
            alerts.validate_threshold('due', {'days_before': '-1',
                                              'overdue_repeat_days': 'x'})
        self.assertEqual(set(caught.exception.message_dict),
                         {'days_before', 'overdue_repeat_days'})
        with self.assertRaises(ValidationError):
            alerts.validate_threshold('missing', {})
        with self.assertRaises(ValidationError):
            alerts.validate_threshold('nope', {})

    def test_a_project_trigger(self):
        alerts.register_trigger('tests.range', 'Range', {
            'low': ('Low', int), 'high': ('High', int)})
        self.addCleanup(alerts.triggers.TRIGGERS.pop, 'tests.range')
        self.assertEqual(alerts.validate_threshold('tests.range',
                                                   {'low': '1', 'high': '5'}),
                         {'low': 1, 'high': 5})
        self.assertIn(('tests.range', 'Range'), alerts.trigger_choices())


class AlertTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user('ana', email='ana@example.com')
        cls.beto = User.objects.create_user('beto', email='')
        cls.balance = Equipment.objects.create(
            name='Balance LB-127', next_calibration=TODAY + timedelta(10))

    def setUp(self):
        self.channel = RecordingChannel()
        saved = dict(channels_module.CHANNELS)
        self.addCleanup(lambda: (channels_module.CHANNELS.clear(),
                                 channels_module.CHANNELS.update(saved)))
        channels_module.CHANNELS.clear()
        alerts.register_channel(self.channel)
        self.evaluated = []
        alerts.register_alert_process(
            PROCESS, 'Equipment due', self.evaluate, [alerts.TRIGGER_DUE],
            permission='demoapp.change_equipment',
            notification_code='equipment-due')
        self.addCleanup(registry.ALERT_PROCESSES.pop, PROCESS, None)
        self.rule = AlertRule.objects.create(
            name='Calibration', process=PROCESS, trigger='due',
            threshold={'days_before': 30, 'overdue_repeat_days': 7},
            created_by=self.ana)
        self.rule.notify_users.add(self.beto)

    def evaluate(self, rule, today=None):
        self.evaluated.append(rule)
        for equipment in Equipment.objects.all():
            alerts.fire_due_alert(rule, equipment, equipment.next_calibration,
                                  'Calibrate %s' % equipment, today=today,
                                  link='/equipment/%d/' % equipment.pk)


class FireTests(AlertTestCase):

    def test_fire_records_and_notifies(self):
        event = alerts.fire_alert(self.rule, 'Hello', self.balance, link='/x/',
                                  context={'extra': 1})
        self.assertEqual(event.content_object, self.balance)
        self.assertEqual(event.level, 'medium')
        self.assertEqual(sorted(event.recipients), ['ana', 'beto'])
        self.assertIsNotNone(event.last_notified_at)
        (sent_event, users, context), = self.channel.sent
        self.assertEqual(sent_event, event)
        self.assertEqual({u.username for u in users}, {'ana', 'beto'})
        self.assertEqual(context['extra'], 1)
        self.assertEqual(context['object'], self.balance)
        self.assertEqual(context['rule'], self.rule)

    def test_the_generic_relation_lists_the_alerts(self):
        event = alerts.fire_alert(self.rule, 'Hello', self.balance)
        self.assertEqual(list(self.balance.alerts.all()), [event])
        self.assertEqual(list(AlertEvent.objects.filter(
            equipment__name='Balance LB-127')), [event])

    def test_recipients_given_or_callable(self):
        event = alerts.fire_alert(self.rule, 'x', recipients=[self.beto, None])
        self.assertEqual(event.recipients, ['beto'])
        event = alerts.fire_alert(self.rule, 'y',
                                  recipients=lambda rule, obj: [self.ana])
        self.assertEqual(event.recipients, ['ana'])

    def test_an_open_dedupe_key_fires_once(self):
        first = alerts.fire_alert(self.rule, 'x', self.balance, dedupe_key='k')
        second = alerts.fire_alert(self.rule, 'x', self.balance, dedupe_key='k')
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(len(self.channel.sent), 1)
        alerts.resolve_alert(first)
        third = alerts.fire_alert(self.rule, 'x', self.balance, dedupe_key='k')
        self.assertNotEqual(third.pk, first.pk)

    def test_renotify_after(self):
        event = alerts.fire_alert(self.rule, 'x', dedupe_key='k')
        alerts.fire_alert(self.rule, 'x', dedupe_key='k',
                          renotify_after=timedelta(days=7))
        self.assertEqual(len(self.channel.sent), 1)
        AlertEvent.objects.filter(pk=event.pk).update(
            last_notified_at=timezone.now() - timedelta(days=8))
        alerts.fire_alert(self.rule, 'x', dedupe_key='k',
                          renotify_after=timedelta(days=7))
        self.assertEqual(len(self.channel.sent), 2)

    def test_the_database_refuses_two_open_events_with_one_key(self):
        alerts.fire_alert(self.rule, 'x', dedupe_key='k')
        real_filter = AlertEvent.objects.filter

        def no_open_found(*args, **kwargs):
            # Simulate the race: the lookup misses the event just created.
            if kwargs.get('dedupe_key') == 'k' and 'pk' not in kwargs:
                return real_filter(pk=-1)
            return real_filter(*args, **kwargs)

        with mock.patch.object(AlertEvent.objects, 'filter', no_open_found):
            again = alerts.fire_alert(self.rule, 'x', dedupe_key='k')
        self.assertEqual(AlertEvent.objects.filter(dedupe_key='k').count(), 1)
        self.assertEqual(again.dedupe_key, 'k')

    def test_a_broken_channel_does_not_stop_the_others(self):
        alerts.register_channel(BrokenChannel())
        with self.assertLogs('djgentelella.alerts.engine', 'ERROR'):
            alerts.fire_alert(self.rule, 'x')
            alerts.resolve_alert(self.rule.events.get())
        self.assertEqual(len(self.channel.sent), 1)
        self.assertEqual(len(self.channel.resolved), 1)

    def test_a_process_picks_its_channels(self):
        other = RecordingChannel()
        other.name = 'other'
        alerts.register_channel(other)
        alerts.register_alert_process(PROCESS, 'Equipment due', self.evaluate,
                                      ['due'], channels=['other'])
        alerts.fire_alert(self.rule, 'x')
        self.assertEqual(self.channel.sent, [])
        self.assertEqual(len(other.sent), 1)


class DueTests(AlertTestCase):

    def test_not_near_does_not_fire(self):
        self.assertIsNone(alerts.fire_due_alert(
            self.rule, self.balance, TODAY + timedelta(31), 'x', today=TODAY))

    def test_upcoming_then_overdue_repeats_every_n_days(self):
        due = self.balance.next_calibration
        event = alerts.fire_due_alert(self.rule, self.balance, due, 'x',
                                      today=TODAY)
        self.assertEqual(self.channel.sent[0][2]['status'], 'upcoming')
        # Overdue, but notified just now: not again yet.
        alerts.fire_due_alert(self.rule, self.balance, due, 'x',
                              today=due + timedelta(1))
        self.assertEqual(len(self.channel.sent), 1)
        AlertEvent.objects.filter(pk=event.pk).update(
            last_notified_at=timezone.now() - timedelta(days=8))
        again = alerts.fire_due_alert(self.rule, self.balance, due, 'x',
                                      today=due + timedelta(9))
        self.assertEqual(again.pk, event.pk)
        self.assertEqual(self.channel.sent[1][2]['status'], 'overdue')

    def test_the_evidence_resolves_and_a_new_date_is_a_new_alert(self):
        event = alerts.fire_due_alert(self.rule, self.balance,
                                      self.balance.next_calibration, 'x',
                                      today=TODAY)
        calibration = Calibration.objects.create(equipment=self.balance,
                                                 done=TODAY)
        closed = alerts.resolve_alert(self.balance, resolution=calibration,
                                      user=self.ana)
        self.assertEqual(closed, [event])
        event.refresh_from_db()
        self.assertIsNotNone(event.resolved_at)
        self.assertEqual(event.resolved_by, self.ana)
        self.assertEqual(event.resolution, calibration)
        self.assertEqual(self.channel.resolved[0][1], calibration)
        self.assertEqual(alerts.resolve_alert(self.balance), [])

        later = alerts.fire_due_alert(self.rule, self.balance,
                                      TODAY + timedelta(365), 'x',
                                      today=TODAY + timedelta(340))
        self.assertNotEqual(later.pk, event.pk)

    def test_resolve_by_rule_and_key_and_anonymous_user(self):
        event = alerts.fire_alert(self.rule, 'x', dedupe_key='k')
        closed = alerts.resolve_alert(rule=self.rule, dedupe_key='k',
                                      user=AnonymousUser())
        self.assertEqual(closed, [event])
        event.refresh_from_db()
        self.assertIsNone(event.resolved_by)
        with self.assertRaises(ValueError):
            alerts.resolve_alert()


class ProcessTests(AlertTestCase):

    def test_run_alert_rules_evaluates_the_active_rules(self):
        AlertRule.objects.create(name='Off', process=PROCESS, trigger='due',
                                 threshold={'days_before': 1}, is_active=False)
        self.assertEqual(alerts.run_alert_rules(PROCESS, today=TODAY), 1)
        self.assertEqual(self.evaluated, [self.rule])
        self.assertEqual(self.balance.alerts.count(), 1)
        # Evaluating again does not duplicate.
        alerts.run_alert_rules(PROCESS, today=TODAY)
        self.assertEqual(self.balance.alerts.count(), 1)
        self.assertEqual(alerts.run_alert_rules('nope'), 0)

    def test_a_failing_rule_does_not_stop_the_others(self):
        AlertRule.objects.create(name='Second', process=PROCESS, trigger='due',
                                 threshold={'days_before': 1})

        def evaluate(rule, **kwargs):
            if rule.name == 'Calibration':
                raise RuntimeError('broken')
            self.evaluated.append(rule)

        alerts.register_alert_process(PROCESS, 'x', evaluate, ['due'])
        with self.assertLogs('djgentelella.alerts.engine', 'ERROR'):
            self.assertEqual(alerts.run_alert_rules(PROCESS), 2)
        self.assertEqual([rule.name for rule in self.evaluated], ['Second'])

    def test_an_evaluator_by_dotted_path(self):
        alerts.register_alert_process(PROCESS, 'x',
                                      'djgentelella.tests.Alerts_Test.dotted',
                                      ['due'])
        DOTTED.clear()
        alerts.run_alert_rules(PROCESS)
        self.assertEqual(DOTTED, [self.rule.pk])

    def test_processes_for(self):
        self.assertEqual(alerts.processes_for(AnonymousUser()), {})
        self.assertNotIn(PROCESS, alerts.processes_for(self.beto))
        self.beto.user_permissions.add(Permission.objects.get(
            codename='change_equipment'))
        beto = User.objects.get(pk=self.beto.pk)
        self.assertIn(PROCESS, alerts.processes_for(beto))

    def test_rule_clean(self):
        self.rule.threshold = {'days_before': '5'}
        self.rule.full_clean()
        self.assertEqual(self.rule.threshold,
                         {'days_before': 5, 'overdue_repeat_days': 0})
        self.rule.trigger = 'percent'
        with self.assertRaises(ValidationError) as caught:
            self.rule.full_clean()
        self.assertIn('trigger', caught.exception.message_dict)
        self.rule.trigger, self.rule.threshold = 'due', {}
        with self.assertRaises(ValidationError) as caught:
            self.rule.full_clean()
        self.assertIn('threshold', caught.exception.message_dict)
        self.rule.process = 'nope'
        with self.assertRaises(ValidationError):
            self.rule.full_clean()

    def test_the_event_model_is_found_from_the_rule(self):
        self.assertIs(AlertRule.get_event_model(), AlertEvent)
        self.assertIs(alerts.get_rule_model(), AlertRule)
        self.assertEqual(self.rule.get_notification_code(), 'equipment-due')


DOTTED = []


def dotted(rule, **kwargs):
    DOTTED.append(rule.pk)


class BuiltinChannelTests(AlertTestCase):

    def test_notification_channel_by_level(self):
        alerts.register_channel(alerts.NotificationChannel(levels=['critical']))
        alerts.fire_alert(self.rule, 'quiet', link='/a/')
        self.assertFalse(Notification.objects.exists())
        self.rule.level = 'critical'
        alerts.fire_alert(self.rule, 'loud', link='/b/')
        notes = Notification.objects.order_by('user__username')
        self.assertEqual([(n.user.username, n.message_type, n.link) for n in notes],
                         [('ana', 'danger', '/b/'), ('beto', 'danger', '/b/')])

    def test_email_channel_with_a_sender(self):
        calls = []
        alerts.register_channel(alerts.EmailChannel(
            sender=lambda event, code, emails, context: calls.append(
                (code, emails, context['message']))))
        alerts.fire_alert(self.rule, 'Check it')
        # beto has no email.
        self.assertEqual(calls, [('equipment-due', ['ana@example.com'],
                                  'Check it')])

    def test_email_channel_through_async_notification(self):
        alerts.register_channel(alerts.EmailChannel())
        with mock.patch('djgentelella.async_notification.sending.'
                        'send_email_from_template') as send:
            alerts.fire_alert(self.rule, 'Check it')
        code, emails, context = send.call_args.args
        self.assertEqual((code, emails), ('equipment-due', ['ana@example.com']))
        self.assertEqual(context['message'], 'Check it')

    def test_no_template_no_email(self):
        alerts.register_channel(alerts.EmailChannel())
        registry.ALERT_PROCESSES[PROCESS].notification_code = ''
        with mock.patch('djgentelella.async_notification.sending.'
                        'send_email_from_template') as send:
            alerts.fire_alert(self.rule, 'x')
        send.assert_not_called()
