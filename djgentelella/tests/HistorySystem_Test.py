"""W21: system events in the history (``add_log(None, ..., system=True)``),
the ``SECRET_READ`` action and the actions a project registers."""

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from djgentelella.history.filterset import HistoryFilterSet
from djgentelella.history.serializers import HistorySerializer
from djgentelella.history.utils import (
    ACTIONS, SECRET_READ, action_label, add_log, register_action, system_user,
)
from djgentelella.models import MenuItem

__all__ = ['SystemEventTests', 'RegisteredActionTests']

User = get_user_model()


def relations(entry):
    return [relation.data for relation in entry.gt_relations.all()]


@override_settings(LANGUAGE_CODE='en')
class SystemEventTests(TestCase):
    def setUp(self):
        self.item = MenuItem.objects.create(title='Credentials', url_name='/x/',
                                            category='main')

    def test_a_system_event_without_a_user(self):
        entry = add_log(None, self.item, SECRET_READ, system=True,
                        actor='rotate_credentials', extra={'event': 'used'})
        account = User.objects.get(username='gt-system')
        self.assertEqual(entry.user, account)
        self.assertFalse(account.is_active)
        self.assertFalse(account.has_usable_password())
        self.assertEqual(relations(entry), [{'event': 'used', 'gt_system': True,
                                             'gt_actor': 'rotate_credentials'}])
        # The account is created once.
        add_log(None, self.item, CHANGE, system=True)
        self.assertEqual(User.objects.filter(username='gt-system').count(), 1)
        self.assertEqual(LogEntry.objects.filter(user=account).count(), 2)

    @override_settings(GT_HISTORY_SYSTEM_USERNAME='robot')
    def test_an_account_of_the_project(self):
        robot = User.objects.create_user('robot')
        entry = add_log(None, self.item, CHANGE, system=True)
        self.assertEqual(entry.user, robot)
        self.assertEqual(system_user(), robot)

    def test_the_flag_takes_no_user(self):
        user = User.objects.create_user('ana')
        with self.assertRaises(ValueError):
            add_log(user, self.item, CHANGE, system=True)
        self.assertFalse(LogEntry.objects.exists())

    @override_settings(GT_HISTORY_ANONYMOUS_USERNAME=None)
    def test_no_user_without_the_flag_is_refused_as_before(self):
        with self.assertRaises(ValueError):
            add_log(None, self.item, CHANGE)
        self.assertFalse(User.objects.filter(username='gt-system').exists())

    def test_the_history_filters_system_events(self):
        add_log(None, self.item, SECRET_READ, system=True, actor='job')
        user = User.objects.create_superuser('root', 'r@example.com', 'x')
        add_log(user, self.item, CHANGE)
        found = HistoryFilterSet({'extra': '{"gt_system": true}'},
                                 queryset=LogEntry.objects.all()).qs
        self.assertEqual([entry.action_flag for entry in found], [SECRET_READ])
        found = HistoryFilterSet({'action_flag': str(SECRET_READ)},
                                 queryset=LogEntry.objects.all()).qs
        self.assertEqual(found.count(), 1)


@override_settings(LANGUAGE_CODE='en')
class RegisteredActionTests(TestCase):
    def setUp(self):
        self._actions = dict(ACTIONS)
        self.addCleanup(self.restore)
        self.item = MenuItem.objects.create(title='Item', url_name='/x/',
                                            category='main')
        self.user = User.objects.create_superuser('root', 'r@example.com', 'x')

    def restore(self):
        ACTIONS.clear()
        ACTIONS.update(self._actions)

    def test_secret_read_is_an_action_of_its_own(self):
        self.assertEqual(SECRET_READ, 6)
        self.assertEqual(action_label(SECRET_READ), 'secret read')
        entry = add_log(self.user, self.item, SECRET_READ)
        self.assertEqual(HistorySerializer(entry).data['action_flag'], 'Secret read')
        self.assertIn('secret read', entry.change_message)

    def test_register_an_action(self):
        self.assertEqual(register_action(120, 'exported'), 120)
        register_action(120, 'exported')  # the same again is fine
        entry = add_log(self.user, self.item, 120)
        self.assertEqual(HistorySerializer(entry).data['action_flag'], 'Exported')
        # The filter offers it, though it was registered after import.
        choices = dict(HistoryFilterSet().filters['action_flag'].field.choices)
        self.assertEqual(choices[120], 'exported')
        found = HistoryFilterSet({'action_flag': '120'},
                                 queryset=LogEntry.objects.all()).qs
        self.assertEqual(list(found), [entry])

    def test_bad_registrations(self):
        for flag in (0, -1, True, 'x', 1, 4, SECRET_READ):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                register_action(flag, 'nope')
        register_action(130, 'one')
        with self.assertRaises(ValueError):
            register_action(130, 'another')

    @override_settings(GT_HISTORY_ALLOWED_MODELS=['djgentelella.menuitem'])
    def test_the_history_api_shows_it(self):
        register_action(140, 'archived')
        add_log(self.user, self.item, 140)
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get(reverse('api-history-list'), {'action_flag': 140})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['action_flag'] for row in response.json()['data']],
                         ['Archived'])
