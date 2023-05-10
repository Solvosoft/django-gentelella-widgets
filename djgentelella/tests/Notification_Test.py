from django.conf import settings
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from demoapp.views import create_notification
from rest_framework import status
from djgentelella.notification.base import NotificationViewSet
from rest_framework.test import APIClient
from rest_framework_datatables.pagination import DatatablesPageNumberPagination


class ApiNotificationsTestCase(TestCase):
    def setUp(self):
        self.api_client = APIClient()
        self.client = Client()
        NotificationViewSet.pagination_class = DatatablesPageNumberPagination
        self.factory = RequestFactory()
        self.first_user = User.objects.create_superuser(
            username='first_user', password='fuser123')
        self.second_user = User.objects.create_superuser(
            username='second_user', password='suser123')
        self.third_user = User.objects.create_superuser(
            username='third_user', password='tuser123')

        total_notifications = 1
        while total_notifications < 4:
            self.set_notifications(total_notifications)
            total_notifications += 1

    def set_notifications(self, total_notifications: int):
        request = self.factory.get(reverse('create_notification'))
        user = self.first_user
        if total_notifications > 2:
            user = self.third_user
        elif total_notifications > 1:
            user = self.second_user

        for counter in range(total_notifications):
            create_notification("Test notification for users", user,
                                'success', link='notifications',
                                link_prop={'args': [], 'kwargs': {'pk': 2}},
                                request=request)

    def test_no_datatables_query_if_not_logged_in(self):
        response = self.api_client.get('/tableapi/notificationtableview/?format=datatables')
        result = response.json()
        expected = 'No encontrado.'
        self.assertFalse('recordsTotal' in result)
        self.assertEqual(result['detail'], expected)

    def test_datatables_query_for_logged_user(self):
        self.api_client.login(username='first_user', password='fuser123')
        response = self.api_client.get('/tableapi/notificationtableview/')
        self.client.logout()
        expected = 1
        result = response.json()
        self.assertFalse('count' in result)
        self.assertTrue('recordsTotal' in result)
        self.assertTrue('recordsFiltered' in result)
        self.assertEqual(result['recordsTotal'], expected)

    def test_get_message_for_not_logged_in_user(self):
        response = self.api_client.get('/notification/2')
        result = response.json()
        expected = 'Las credenciales de autenticación no se proveyeron.'
        self.assertFalse('count' in result)
        self.assertFalse('results' in result)
        self.assertEqual(result['detail'], expected)

    def test_get_notification_info_by_pk(self):
        self.api_client.login(username='third_user', password='tuser123')
        response = self.api_client.get('/notification/2')
        self.api_client.logout()
        result = response.json()
        expected = 3
        self.assertEqual(result['count'], expected)
        self.assertTrue("results" in result)

    def test_page_found_but_needs_login(self):
        response = self.client.get('/notification_datatable_view')
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

    def test_page_redirects_for_non_logged_in_user(self):
        response = self.client.get('/notification_datatable_view', follow=True)
        self.assertRedirects(response, settings.LOGIN_URL)

    def test_page_ok_for_logged_in(self):
        self.client.login(username='second_user', password='suser123')
        response = self.client.get('/notification_datatable_view')
        self.client.logout()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # self.assertContains()
