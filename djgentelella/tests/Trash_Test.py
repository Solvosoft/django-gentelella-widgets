"""Error contract of the trash restore endpoint.

The trash page has no library javascript of its own: every project writes the
``restore`` caller itself, copying the one in
``demoapp/templates/gentelella/trash/trash.html``. That caller reads the failure
message out of the response body, so the *shape* of an error answer is part of
the endpoint's public contract, not an implementation detail -- these tests pin
it. What matters to the caller is that a failure is always JSON carrying a
``detail``, never Django's HTML error page.
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from demoapp.models import Customer
from djgentelella.models import Trash


class TrashRestoreErrorContractTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='trashadmin', email='trash@example.com',
            password='restoring')
        self.api_client = APIClient()
        self.api_client.force_authenticate(self.user)

    def restore_url(self, pk):
        return reverse('api-trash-restore', args=[pk])

    def make_trash(self):
        customer = Customer.objects.create(
            name='cliente borrado', phone_number='4444-4444',
            email='borrado@example.com')
        return Trash.objects.create(
            content_type=ContentType.objects.get_for_model(Customer),
            object_id=customer.pk, deleted_by=self.user)

    def test_restoring_brings_the_object_back(self):
        trash = self.make_trash()
        response = self.api_client.post(self.restore_url(trash.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()['result'])

    def test_a_missing_entry_is_a_404_in_json(self):
        """The pk is gone -- someone else restored it from another tab.

        A 404, not the 400 this used to answer: the catch-all around the restore
        swallowed the ``Http404`` and reported it as a failed restore. DRF's
        exception handler serialises it, so the body stays JSON with a
        ``detail`` -- the caller shows that string to the user, and an HTML
        error page would leave it with nothing to show.
        """
        response = self.api_client.post(self.restore_url(999999))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertIn('detail', response.json())

    def test_a_failed_restore_still_answers_json_and_reaches_the_log(self):
        """The entry is there but restoring it blows up.

        ``restore()`` reaches arbitrary model code through the generic relation,
        so the catch-all stays -- but the client only ever sees the generic
        message, which makes the log the single place the real reason shows up.
        """
        trash = self.make_trash()
        with mock.patch.object(Trash, 'restore', side_effect=RuntimeError('boom')):
            with self.assertLogs('djgentelella.trash.api', level='ERROR') as logs:
                response = self.api_client.post(self.restore_url(trash.pk))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertFalse(response.json()['result'])
        self.assertIn('boom', logs.output[0])

    def test_without_the_permission_the_refusal_is_json_too(self):
        plain = get_user_model().objects.create_user(
            username='nobody', password='nothing')
        client = APIClient()
        client.force_authenticate(plain)
        trash = self.make_trash()
        response = client.post(self.restore_url(trash.pk))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertIn('detail', response.json())
