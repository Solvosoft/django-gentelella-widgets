from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now
from rest_framework import status
from rest_framework.test import APIClient

from demoapp.models import Community, Country, ObjectManagerDemoModel, \
    ObjectManagerDemoNote
from djgentelella.objectmanagement import BaseInlineObjectManagement


class InlineObjectManagementTestCase(TestCase):
    """BaseInlineObjectManagement scopes every action to its parent object."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='editor', password='editing')
        self.api_client = APIClient()
        self.api_client.force_authenticate(self.user)
        self.client.force_login(self.user)
        country = Country.objects.create(name='Costa Rica')
        community = Community.objects.create(name='community')
        self.first = self.create_demo_object('first', country, community)
        self.second = self.create_demo_object('second', country, community)

        self.first_note = ObjectManagerDemoNote.objects.create(
            demo_object=self.first, title='first note', body='body one')
        self.second_note = ObjectManagerDemoNote.objects.create(
            demo_object=self.second, title='second note', body='body two')

    def create_demo_object(self, name, country, community):
        return ObjectManagerDemoModel.objects.create(
            name=name, born_date=now().date(), last_time=now(),
            livetime_range='', description='', radio_elements=1,
            taging_list='', field_autocomplete=country, field_select=community)

    def list_url(self, parent):
        return reverse('api-objectmanagement-note-list', args=[parent.pk])

    def detail_url(self, parent, note):
        return reverse('api-objectmanagement-note-detail',
                       args=[parent.pk, note.pk])

    def test_list_only_returns_notes_of_the_parent(self):
        # limit/offset are what the datatable sends on every draw
        response = self.api_client.get(self.list_url(self.first),
                                       {'limit': 10, 'offset': 0})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [row['title'] for row in response.data['data']]
        self.assertEqual(titles, ['first note'])
        self.assertEqual(response.data['recordsTotal'], 1)

    def test_list_of_unknown_parent_is_not_found(self):
        response = self.api_client.get(
            reverse('api-objectmanagement-note-list', args=[0]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_assigns_the_parent_from_the_url(self):
        response = self.api_client.post(
            self.list_url(self.second), {'title': 'new note', 'body': 'text'},
            format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        note = ObjectManagerDemoNote.objects.get(title='new note')
        self.assertEqual(note.demo_object, self.second)

    def test_retrieve_of_a_note_from_another_parent_is_not_found(self):
        response = self.api_client.get(
            self.detail_url(self.first, self.second_note))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_keeps_the_note_on_its_parent(self):
        response = self.api_client.put(
            self.detail_url(self.first, self.first_note),
            {'title': 'renamed', 'body': 'body one'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.first_note.refresh_from_db()
        self.assertEqual(self.first_note.title, 'renamed')
        self.assertEqual(self.first_note.demo_object, self.first)

    def test_inline_page_renders(self):
        response = self.client.get(
            reverse('object_management_inline', args=[self.first.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, self.list_url(self.first))

    def test_delete_of_a_note_from_another_parent_is_not_found(self):
        response = self.api_client.delete(
            self.detail_url(self.first, self.second_note))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(
            ObjectManagerDemoNote.objects.filter(pk=self.second_note.pk).exists())

    def test_an_anonymous_client_cannot_touch_the_notes(self):
        # the documented example: whoever copies it should not be copying an
        # open endpoint
        anonymous = APIClient()
        self.assertIn(anonymous.get(self.list_url(self.first)).status_code,
                      (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        response = anonymous.post(self.list_url(self.first),
                                  {'title': 'anon', 'body': 'text'},
                                  format='json')
        self.assertIn(response.status_code,
                      (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        self.assertFalse(
            ObjectManagerDemoNote.objects.filter(title='anon').exists())

    def test_a_parent_sent_in_the_body_does_not_override_the_url(self):
        # The url is the only place the parent may come from: the parent decides
        # what the request may reach, and DRF permissions are per model, so a
        # client-chosen parent would let anyone write into someone else's object.
        response = self.api_client.post(
            self.list_url(self.first),
            {'title': 'smuggled', 'body': 'text',
             'parent_pk': self.second.pk, 'demo_object': self.second.pk},
            format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        note = ObjectManagerDemoNote.objects.get(title='smuggled')
        self.assertEqual(note.demo_object, self.first)

    def test_a_parent_in_the_query_string_is_ignored(self):
        response = self.api_client.get(
            self.list_url(self.first),
            {'limit': 10, 'offset': 0, 'parent_pk': self.second.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [row['title'] for row in response.data['data']]
        self.assertEqual(titles, ['first note'])

    def test_a_viewset_without_the_parent_settings_is_a_configuration_error(self):
        viewset = BaseInlineObjectManagement()
        viewset.kwargs = {'parent_pk': self.first.pk}
        with self.assertRaises(ImproperlyConfigured):
            viewset.get_parent_object()
