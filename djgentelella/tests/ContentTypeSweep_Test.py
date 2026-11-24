"""
The views of djgentelella that take a content type from the client and stay
as they are (W19 sweep): the label only narrows a list the user may already
read, and never widens it.

The hardened ones are tested where they live: the signature in
``FirmadorAccess_Test`` and ``SignatureForm_Test``, async_notification in
``djgentelella/async_notification/tests/test_security.py``.
"""
from django.contrib.admin.models import ADDITION
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from demoapp.models import Customer
from djgentelella.history.utils import add_log
from djgentelella.utils import contenttypes_from_labels

BAD_LABELS = ('nope', 'auth.nomodel', '', '.', 'demoapp.', '.customer')


class ContentTypeLabelsTests(TestCase):
    def test_a_bad_label_is_no_content_type(self):
        for label in BAD_LABELS + (None, 3, ['auth.user']):
            self.assertFalse(contenttypes_from_labels([label]).exists(), label)


class SweepTestCase(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username='sweeper', email='s@example.com', password='x')
        self.api_client = APIClient()
        self.api_client.force_authenticate(self.admin)
        self.customer = Customer.objects.create(
            name='cliente', phone_number='1', email='c@example.com')

    def rows(self, name, params):
        response = self.api_client.get(reverse(name), {**params, 'limit': 50,
                                                       'offset': 0})
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()


class HistoryContentTypeTests(SweepTestCase):
    def setUp(self):
        super().setUp()
        add_log(self.admin, self.customer, ADDITION, change_message='x',
                related_objects=[self.customer])
        add_log(self.admin, self.admin, ADDITION, change_message='x')

    @override_settings(GT_HISTORY_ALLOWED_MODELS=None)
    def test_a_bad_related_label_lists_nothing(self):
        self.assertEqual(self.rows('api-history-list', {})['recordsTotal'], 2)
        for label in BAD_LABELS[:2] + BAD_LABELS[3:]:
            payload = self.rows('api-history-list', {'related_contenttype': label})
            self.assertEqual(payload['recordsFiltered'], 0, label)

    @override_settings(GT_HISTORY_ALLOWED_MODELS=['demoapp.customer'])
    def test_the_contenttype_param_cannot_leave_the_allowed_models(self):
        payload = self.rows('api-history-list', {'contenttype': 'auth.user'})
        self.assertEqual(payload['recordsTotal'], 1)
        self.assertEqual(payload['recordsFiltered'], 1)


class TrashContentTypeTests(SweepTestCase):
    def test_a_bad_related_label_lists_nothing(self):
        gone = Customer.objects.create(name='x', phone_number='2', email='x@e.com')
        gone.delete(user=self.admin, related_objects=[self.customer])
        self.assertEqual(self.rows('api-trash-list', {})['recordsTotal'], 1)
        for label in ('nope', 'auth.nomodel'):
            payload = self.rows('api-trash-list', {'related_contenttype': label})
            self.assertEqual(payload['recordsTotal'], 0, label)
