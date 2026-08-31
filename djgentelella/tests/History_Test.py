"""Contract of the audit log: what add_log stores and what the API exposes.

The interesting parts are the ones multi-tenant consumers depend on: the
returned entry, the relation rows (one action touching several objects), the
extra JSON payload and its 1..n-key filtering, and a recordsTotal that never
leaks the platform-wide count into a scoped listing.
"""

import json

from django.contrib.admin.models import ADDITION, DELETION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from demoapp.models import Customer
from djgentelella.history.api import BaseViewSetWithLogs
from djgentelella.history.utils import add_log
from djgentelella.models import HistoryRelation, Trash


class AddLogTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='auditor', password='logging')
        self.customer = Customer.objects.create(
            name='cliente', phone_number='1111-1111', email='c@example.com')

    def test_returns_the_created_entry(self):
        entry = add_log(self.user, self.customer, ADDITION,
                        change_message='Created')
        self.assertIsInstance(entry, LogEntry)
        self.assertEqual(entry.object_id, str(self.customer.pk))

    def test_related_objects_become_relation_rows(self):
        other = Customer.objects.create(
            name='otro', phone_number='2', email='o@example.com')
        entry = add_log(
            self.user, self.customer, ADDITION, change_message='Created',
            related_objects=[other, (self.customer, {'role': 'self'})])
        rows = HistoryRelation.objects.filter(log_entry=entry).order_by('id')
        self.assertEqual(rows.count(), 2)
        self.assertEqual(rows[0].content_object, other)
        self.assertIsNone(rows[0].data)
        self.assertEqual(rows[1].data, {'role': 'self'})

    def test_a_single_instance_is_accepted(self):
        entry = add_log(self.user, self.customer, ADDITION,
                        change_message='x', related_objects=self.customer)
        self.assertEqual(entry.gt_relations.count(), 1)

    def test_extra_is_stored_as_a_targetless_row(self):
        entry = add_log(self.user, self.customer, ADDITION,
                        change_message='x',
                        extra={'user_agent': 'probe', 'org': 7})
        row = entry.gt_relations.get(content_type__isnull=True)
        self.assertEqual(row.data['org'], 7)
        self.assertIsNone(row.object_id)

    def test_a_bare_pk_is_rejected(self):
        """A pk without a model is how audit trails point at the wrong table."""
        with self.assertRaises(ValueError):
            add_log(self.user, self.customer, ADDITION,
                    change_message='x', related_objects=[42])

    def test_anonymous_without_setting_is_a_clear_error(self):
        with self.assertRaises(ValueError):
            add_log(AnonymousUser(), self.customer, ADDITION,
                    change_message='x')

    @override_settings(GT_HISTORY_ANONYMOUS_USERNAME='ghost')
    def test_anonymous_goes_to_the_sentinel(self):
        sentinel = get_user_model().objects.create_user(
            username='ghost', password='boo')
        entry = add_log(AnonymousUser(), self.customer, ADDITION,
                        change_message='x')
        self.assertEqual(entry.user, sentinel)

    def test_a_custom_delete_message_is_kept(self):
        """The generic sentence never replaces a message the caller gave."""
        entry = add_log(self.user, self.customer, DELETION,
                        change_message='Deleted the quarterly report')
        self.assertEqual(entry.change_message,
                         'Deleted the quarterly report')

    def test_an_empty_message_gets_the_generic_sentence(self):
        entry = add_log(self.user, self.customer, DELETION)
        self.assertIn(str(self.customer), entry.change_message)


class HistoryEndpointTestCase(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username='histadmin', email='h@example.com', password='reading')
        self.api_client = APIClient()
        self.api_client.force_authenticate(self.admin)
        self.customer = Customer.objects.create(
            name='cliente', phone_number='1', email='c@example.com')
        self.url = reverse('api-history-list')

    def log(self, **kwargs):
        return add_log(self.admin, self.customer, ADDITION,
                       change_message='x', **kwargs)

    def test_contenttype_param_without_the_setting_is_not_a_500(self):
        self.log()
        response = self.api_client.get(
            self.url, {'contenttype': 'demoapp.customer'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['recordsTotal'], 1)

    @override_settings(GT_HISTORY_ALLOWED_MODELS=['demoapp.customer'])
    def test_records_total_is_the_scoped_universe(self):
        """Entries outside the allowed models must not inflate the footer."""
        self.log()
        outsider = get_user_model().objects.create_user(
            username='outsider', password='x')
        add_log(self.admin, outsider, ADDITION, change_message='x')
        response = self.api_client.get(self.url)
        self.assertEqual(response.json()['recordsTotal'], 1)

    def test_filter_by_related_object(self):
        other = Customer.objects.create(
            name='otro', phone_number='2', email='o@example.com')
        wanted = self.log(related_objects=[other])
        self.log()  # unrelated entry
        response = self.api_client.get(self.url, {
            'related_contenttype': 'demoapp.customer',
            'related_id': other.pk,
        })
        payload = response.json()
        self.assertEqual(payload['recordsFiltered'], 1)
        self.assertEqual(payload['data'][0]['id'], wanted.pk)

    def test_filter_by_one_and_many_extra_keys(self):
        wanted = self.log(extra={'org': 1, 'lab': 5})
        self.log(extra={'org': 1, 'lab': 9})
        self.log(extra={'org': 2, 'lab': 5})
        one = self.api_client.get(self.url, {'extra': json.dumps({'org': 2})})
        self.assertEqual(one.json()['recordsFiltered'], 1)
        both = self.api_client.get(
            self.url, {'extra': json.dumps({'org': 1, 'lab': 5})})
        payload = both.json()
        self.assertEqual(payload['recordsFiltered'], 1)
        self.assertEqual(payload['data'][0]['id'], wanted.pk)

    def test_garbage_extra_matches_nothing(self):
        self.log(extra={'org': 1})
        response = self.api_client.get(self.url, {'extra': 'not json'})
        self.assertEqual(response.json()['recordsFiltered'], 0)


class FakeRequest:
    method = 'DELETE'
    path = '/probe/'

    def __init__(self, user):
        self.user = user
        self.META = {'HTTP_USER_AGENT': 'probe-browser',
                     'REMOTE_ADDR': '10.0.0.9'}


class BaseViewSetWithLogsTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='writer', password='x')
        self.customer = Customer.objects.create(
            name='cliente', phone_number='1', email='c@example.com')

    def make_viewset(self, **attrs):
        viewset = BaseViewSetWithLogs()
        viewset.request = FakeRequest(self.user)
        viewset.kwargs = {}
        viewset.get_object = lambda: self.customer
        for name, value in attrs.items():
            setattr(viewset, name, value)
        return viewset

    def test_destroy_without_models_log_does_not_blow_up(self):
        """models_log is optional: with no allowlist, everything is logged."""
        viewset = self.make_viewset()
        viewset.perform_destroy(self.customer)
        entry = LogEntry.objects.latest('pk')
        self.assertEqual(entry.action_flag, DELETION)

    def test_models_log_allowlist_uses_app_label_model(self):
        viewset = self.make_viewset(models_log=['demoapp.customer'])
        self.assertTrue(viewset.should_log(self.customer))
        viewset = self.make_viewset(models_log=['otherapp.customer'])
        self.assertFalse(viewset.should_log(self.customer))

    def test_destroy_records_who_threw_it_away(self):
        viewset = self.make_viewset()
        viewset.perform_destroy(self.customer)
        trash = Trash.objects.get(
            content_type=ContentType.objects.get_for_model(Customer),
            object_id=self.customer.pk)
        self.assertEqual(trash.deleted_by, self.user)

    def test_request_metadata_reaches_the_log(self):
        viewset = self.make_viewset()
        viewset.perform_destroy(self.customer)
        entry = LogEntry.objects.latest('pk')
        row = entry.gt_relations.get(content_type__isnull=True)
        self.assertEqual(row.data['user_agent'], 'probe-browser')
        self.assertEqual(row.data['ip'], '10.0.0.9')

    def test_bulk_queryset_delete_leaves_trash_rows(self):
        Customer.objects.create(name='dos', phone_number='2',
                                email='d@example.com')
        Customer.objects.all().delete(user=self.user)
        self.assertEqual(Customer.objects.count(), 0)
        self.assertEqual(Customer.objects_deleted_only.count(), 2)
        self.assertEqual(
            Trash.objects.filter(deleted_by=self.user).count(), 2)
