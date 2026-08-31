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
from djgentelella.models import Trash, TrashRelation
from djgentelella.trash.api import TrashViewSet


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

    def make_orphan_trash(self):
        return Trash.objects.create(
            content_type=ContentType.objects.get_for_model(Customer),
            object_id=987654, deleted_by=self.user)

    def test_restore_honours_the_scoped_queryset(self):
        """A multi-tenant subclass narrows get_queryset(); restore must not
        reach entries outside it."""
        trash = self.make_trash()
        with mock.patch.object(TrashViewSet, 'get_queryset',
                               return_value=Trash.objects.none()):
            response = self.api_client.post(self.restore_url(trash.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_restoring_an_orphan_is_410_gone(self):
        """The original object was hard-deleted elsewhere: nothing to bring
        back, and the caller is told so instead of a generic failure."""
        trash = self.make_orphan_trash()
        response = self.api_client.post(self.restore_url(trash.pk))
        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertFalse(response.json()['result'])

    def test_hard_deleting_an_orphan_removes_the_row(self):
        """Nothing to hard delete but the entry itself, which must go."""
        trash = self.make_orphan_trash()
        trash.hard_delete()
        self.assertFalse(Trash.objects.filter(pk=trash.pk).exists())


class TrashRelationTestCase(TestCase):
    """The deletion context: TrashRelation rows written by delete() and the
    scoping they enable on the trash endpoint."""

    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='trashadmin', email='trash@example.com',
            password='restoring')
        self.api_client = APIClient()
        self.api_client.force_authenticate(self.user)
        self.context = Customer.objects.create(
            name='la organización', phone_number='1', email='org@example.com')

    def make_customer(self, name='borrable'):
        return Customer.objects.create(
            name=name, phone_number='2222-2222', email='b@example.com')

    def trash_of(self, obj):
        return Trash.objects.get(
            content_type=ContentType.objects.get_for_model(Customer),
            object_id=obj.pk)

    def test_delete_records_the_relations(self):
        customer = self.make_customer()
        customer.delete(user=self.user, related_objects=[self.context])
        trash = self.trash_of(customer)
        relations = trash.gt_relations.all()
        self.assertEqual(relations.count(), 1)
        self.assertEqual(relations[0].content_object, self.context)

    def test_a_single_instance_needs_no_list(self):
        customer = self.make_customer()
        customer.delete(user=self.user, related_objects=self.context)
        self.assertEqual(self.trash_of(customer).gt_relations.count(), 1)

    def test_a_bare_pk_is_rejected(self):
        customer = self.make_customer()
        with self.assertRaises(ValueError):
            customer.delete(user=self.user,
                            related_objects=[self.context.pk])

    def test_a_redeleted_entry_keeps_its_original_context(self):
        # A model-level restore() leaves the Trash row standing (only
        # Trash.restore() removes it), so a re-delete meets an entry that
        # already has its context: the first deletion wins.
        customer = self.make_customer()
        customer.delete(user=self.user, related_objects=[self.context])
        customer.restore()
        other = self.make_customer('otro contexto')
        customer.delete(user=self.user, related_objects=[other])
        trash = self.trash_of(customer)
        self.assertEqual(
            [r.content_object for r in trash.gt_relations.all()],
            [self.context])

    def test_a_restored_then_redeleted_entry_gets_the_new_context(self):
        # Restoring through the Trash row removes it (and its relations by
        # cascade): the next deletion starts a fresh entry with the new
        # context.
        customer = self.make_customer()
        customer.delete(user=self.user, related_objects=[self.context])
        self.trash_of(customer).restore()
        customer.refresh_from_db()
        other = self.make_customer('otro contexto')
        customer.delete(user=self.user, related_objects=[other])
        trash = self.trash_of(customer)
        self.assertEqual(
            [r.content_object for r in trash.gt_relations.all()], [other])

    def test_queryset_delete_records_the_relations(self):
        one = self.make_customer('uno')
        two = self.make_customer('dos')
        Customer.objects.filter(pk__in=[one.pk, two.pk]).delete(
            user=self.user, related_objects=[self.context])
        for obj in (one, two):
            self.assertEqual(self.trash_of(obj).gt_relations.count(), 1)

    def test_restore_cascades_the_relations_away(self):
        customer = self.make_customer()
        customer.delete(user=self.user, related_objects=[self.context])
        trash = self.trash_of(customer)
        trash.restore()
        self.assertFalse(
            TrashRelation.objects.filter(trash_id=trash.pk).exists())

    def test_list_filters_by_related_object(self):
        inside = self.make_customer('dentro')
        outside = self.make_customer('fuera')
        inside.delete(user=self.user, related_objects=[self.context])
        outside.delete(user=self.user)
        response = self.api_client.get(
            reverse('api-trash-list'),
            {'related_contenttype': 'demoapp.customer',
             'related_id': self.context.pk,
             'limit': 10, 'offset': 0})
        payload = response.json()
        ids = [row['object_id'] for row in payload['data']]
        self.assertIn(inside.pk, ids)
        self.assertNotIn(outside.pk, ids)
        # recordsTotal follows the narrowed queryset, not the whole table.
        self.assertEqual(payload['recordsTotal'], len(payload['data']))

    def test_scope_queryset_narrows_list_and_count(self):
        gone = self.make_customer()
        gone.delete(user=self.user)
        with mock.patch.object(TrashViewSet, 'scope_queryset',
                               return_value=Trash.objects.none()):
            response = self.api_client.get(
                reverse('api-trash-list'), {'limit': 10, 'offset': 0})
        payload = response.json()
        self.assertEqual(payload['data'], [])
        self.assertEqual(payload['recordsTotal'], 0)
