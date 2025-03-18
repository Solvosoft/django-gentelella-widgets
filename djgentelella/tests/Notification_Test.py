import datetime
import re
import uuid

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import formats
from django.utils.timezone import now
from rest_framework import status
from rest_framework.exceptions import NotFound, NotAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.test import APIClient

from demoapp.views import create_notification
from djgentelella.models import Notification
from djgentelella.notification.base import NotificationViewSet


class ApiNotificationsTestCase(TestCase):
    def setUp(self):
        self.api_client = APIClient()
        self.client = Client()
        NotificationViewSet.pagination_class = PageNumberPagination
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

    def create_notification_for_filters(self, user):
        request = self.factory.get(reverse('create_notification'))
        create_notification("Notification for filters", user,
                            'warning', link='notifications',
                            link_prop={'args': [], 'kwargs': {'pk': 2}},
                            request=request)

    def test_no_datatables_query_if_not_logged_in(self):
        response = self.api_client.get(reverse('api-notificationtable-list') +
                                       "?format=datatables")
        result = response.json()
        expected = NotFound.default_detail
        self.assertFalse('recordsTotal' in result)
        self.assertEqual(result['detail'], expected)

    def test_datatables_query_for_logged_user(self):
        self.api_client.login(username='first_user', password='fuser123')
        response = self.api_client.get(reverse('api-notificationtable-list'))
        self.client.logout()
        expected = 1
        result = response.json()
        self.assertFalse('count' in result)
        self.assertTrue('recordsTotal' in result)
        self.assertTrue('recordsFiltered' in result)
        self.assertEqual(result['recordsTotal'], expected)

    def test_get_message_for_not_logged_in_user(self):
        response = self.api_client.get(reverse('notifications'))
        result = response.json()
        expected = NotAuthenticated.default_detail
        self.assertFalse('count' in result)
        self.assertFalse('results' in result)
        self.assertEqual(result['detail'], expected)

    def test_get_notification_info_by_pk(self):
        self.api_client.login(username='third_user', password='tuser123')
        response = self.api_client.get(reverse('notifications'))
        self.api_client.logout()
        result = response.json()
        expected = 3
        self.assertEqual(result['count'], expected)
        self.assertTrue("results" in result)

    def test_page_found_but_needs_login(self):
        response = self.client.get(reverse('notification_list'))
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

    def test_page_redirects_for_non_logged_in_user(self):
        response = self.client.get(reverse('notification_list'), follow=True)
        self.assertRedirects(response, settings.LOGIN_URL + "?next=" +
                             reverse('notification_list'))

    def test_page_ok_for_logged_in(self):
        self.client.login(username='second_user', password='suser123')
        response = self.client.get(reverse('notification_list'))
        self.client.logout()
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_page_contains_table(self):
        self.client.login(username='second_user', password='suser123')
        response = self.client.get(reverse('notification_list'))
        self.client.logout()
        table_script = '<table id="notificationdatatable" class="table table-striped ' \
                       'table-bordered" style="width:100%"></table>'

        self.assertContains(response, table_script, html=True)

    def test_general_filter_input_by_description_returns_one_record(self):
        self.create_notification_for_filters(self.first_user)
        self.api_client.login(username='first_user', password='fuser123')
        search_script = '?offset=0&limit=10&draw=5&search=filters&' \
                        'ordering=message_type&_=1684193881008'
        response = self.api_client.get(reverse('api-notificationtable-list') +
                                       search_script)
        self.client.logout()
        filtered_expected = 1
        total_expected = 2
        result = response.json()
        self.assertEqual(result['recordsFiltered'], filtered_expected)
        self.assertEqual(result['recordsTotal'], total_expected)

    def test_general_filter_input_by_description_returns_no_records(self):
        self.api_client.login(username='first_user', password='fuser123')
        search_script = '?offset=0&limit=10&draw=5&search=something&' \
                        'ordering=message_type&_=1684193881008'
        response = self.api_client.get(reverse('api-notificationtable-list') +
                                       search_script)
        self.client.logout()
        filtered_expected = 0
        total_expected = 1
        result = response.json()
        self.assertEqual(result['recordsFiltered'], filtered_expected)
        self.assertEqual(result['recordsTotal'], total_expected)

    def test_general_filter_input_by_message_type_returns_one_record(self):
        self.create_notification_for_filters(self.second_user)
        self.api_client.login(username='second_user', password='suser123')
        search_script = '?offset=0&limit=10&draw=5&search=warn&' \
                        'ordering=message_type&_=1684193881008'
        response = self.api_client.get(reverse('api-notificationtable-list') +
                                       search_script)
        self.client.logout()
        filtered_expected = 1
        total_expected = 3
        result = response.json()
        self.assertEqual(result['recordsFiltered'], filtered_expected)
        self.assertEqual(result['recordsTotal'], total_expected)

    def test_general_filter_input_by_message_type_returns_no_records(self):
        self.api_client.login(username='second_user', password='suser123')
        search_script = '?offset=0&limit=10&draw=5&search=something&' \
                        'ordering=message_type&_=1684193881008'
        response = self.api_client.get(reverse('api-notificationtable-list') +
                                       search_script)
        self.client.logout()
        filtered_expected = 0
        total_expected = 2
        result = response.json()
        self.assertEqual(result['recordsFiltered'], filtered_expected)
        self.assertEqual(result['recordsTotal'], total_expected)

    def test_general_filter_input_by_state_returns_one_record(self):
        Notification.objects.create(
            state='hide',
            user=self.second_user,
            message_type='warning',
            description="Notification for filters",
            link='/notification/2/',
            category=uuid.uuid4()
        )
        self.api_client.login(username='second_user', password='suser123')
        search_script = '?offset=0&limit=10&draw=5&search=hid&' \
                        'ordering=message_type&_=1684193881008'
        response = self.api_client.get(reverse('api-notificationtable-list') +
                                       search_script)
        self.client.logout()
        filtered_expected = 1
        total_expected = 3
        result = response.json()
        self.assertEqual(result['recordsFiltered'], filtered_expected)
        self.assertEqual(result['recordsTotal'], total_expected)

    def test_general_filter_input_by_state_returns_no_records(self):
        self.api_client.login(username='second_user', password='suser123')
        search_script = '?offset=0&limit=10&draw=5&search=something&' \
                        'ordering=message_type&_=1684193881008'
        response = self.api_client.get(reverse('api-notificationtable-list') +
                                       search_script)
        self.client.logout()
        filtered_expected = 0
        total_expected = 2
        result = response.json()
        self.assertEqual(result['recordsFiltered'], filtered_expected)
        self.assertEqual(result['recordsTotal'], total_expected)

    def test_message_type_input_filter_returns_one_record(self):
        self.create_notification_for_filters(self.third_user)
        self.api_client.login(username='third_user', password='tuser123')
        search_script = '?offset=0&limit=10&draw=13&message_type=warn&' \
                        'message_type__icontains=warn&ordering=message_type&' \
                        '_=1684194630148'
        response = self.api_client.get(reverse('api-notificationtable-list') +
                                       search_script)
        self.client.logout()
        filtered_expected = 1
        total_expected = 4
        result = response.json()
        self.assertEqual(result['recordsFiltered'], filtered_expected)
        self.assertEqual(result['recordsTotal'], total_expected)

    def test_message_type_input_filter_returns_no_records(self):
        self.api_client.login(username='third_user', password='tuser123')
        search_script = '?offset=0&limit=10&draw=13&message_type=something&' \
                        'message_type__icontains=something&ordering=message_type&' \
                        '_=1684194630148'
        response = self.api_client.get(reverse('api-notificationtable-list') +
                                       search_script)
        self.client.logout()
        filtered_expected = 0
        total_expected = 3
        result = response.json()
        self.assertEqual(result['recordsFiltered'], filtered_expected)
        self.assertEqual(result['recordsTotal'], total_expected)

    def test_creation_date_input_filter_returns_one_record(self):
        start_date = now() + datetime.timedelta(-3)
        end_date = now()
        user_notification = Notification.objects.filter(user=self.third_user)[0]
        user_notification.creation_date += datetime.timedelta(-2)
        user_notification.save()

        range_datetime = start_date.strftime(
            formats.get_format('DATETIME_INPUT_FORMATS')[0]) + ' - ' + \
                         end_date.strftime(
                             formats.get_format('DATETIME_INPUT_FORMATS')[0])

        replace_symbols = {'/': '%2F', ' ': '%20', ':': '%3A'}
        for char in replace_symbols.keys():
            range_datetime = re.sub(char, replace_symbols[char], range_datetime)

        self.api_client.login(username='third_user', password='tuser123')
        search_script = '?offset=0&limit=10&draw=16&creation_date=' + \
                        range_datetime + \
                        '&ordering=message_type&_=1684194630151'
        response = self.api_client.get(reverse('api-notificationtable-list') +
                                       search_script)
        self.client.logout()
        filtered_expected = 1
        total_expected = 3
        result = response.json()
        self.assertEqual(result['recordsFiltered'], filtered_expected)
        self.assertEqual(result['recordsTotal'], total_expected)

    def test_creation_date_input_filter_returns_no_records(self):
        start_date = now() + datetime.timedelta(-3)
        end_date = now() + datetime.timedelta(-2)

        range_datetime = start_date.strftime(
            formats.get_format('DATETIME_INPUT_FORMATS')[0]) + ' - ' + \
                         end_date.strftime(
                             formats.get_format('DATETIME_INPUT_FORMATS')[0])

        replace_symbols = {'/': '%2F', ' ': '%20', ':': '%3A'}
        for char in replace_symbols.keys():
            range_datetime = re.sub(char, replace_symbols[char], range_datetime)

        self.api_client.login(username='third_user', password='tuser123')
        search_script = '?offset=0&limit=10&draw=16&creation_date=' + \
                        range_datetime + \
                        '&ordering=message_type&_=1684194630151'
        response = self.api_client.get(reverse('api-notificationtable-list') +
                                       search_script)
        self.client.logout()
        filtered_expected = 0
        total_expected = 3
        result = response.json()
        self.assertEqual(result['recordsFiltered'], filtered_expected)
        self.assertEqual(result['recordsTotal'], total_expected)

    def test_description_input_filter_returns_one_record(self):
        self.create_notification_for_filters(self.third_user)
        self.api_client.login(username='third_user', password='tuser123')
        search_script = '?offset=0&limit=10&draw=4&description=filte&description' \
                        '__icontains=filte&ordering=message_type&_=1684210238121'
        response = self.api_client.get(reverse('api-notificationtable-list') +
                                       search_script)
        self.client.logout()
        filtered_expected = 1
        total_expected = 4
        result = response.json()
        self.assertEqual(result['recordsFiltered'], filtered_expected)
        self.assertEqual(result['recordsTotal'], total_expected)

    def test_description_input_filter_returns_no_records(self):
        self.api_client.login(username='third_user', password='tuser123')
        search_script = '?offset=0&limit=10&draw=4&description=something&description' \
                        '__icontains=something&ordering=message_type&_=1684210238121'
        response = self.api_client.get(reverse('api-notificationtable-list') +
                                       search_script)
        self.client.logout()
        filtered_expected = 0
        total_expected = 3
        result = response.json()
        self.assertEqual(result['recordsFiltered'], filtered_expected)
        self.assertEqual(result['recordsTotal'], total_expected)

    def test_link_input_filter_returns_one_record(self):
        user_notification = Notification.objects.filter(user=self.third_user)[0]
        user_notification.link = '/testing/link/'
        user_notification.save()

        self.api_client.login(username='third_user', password='tuser123')
        search_script = '?offset=0&limit=10&draw=11&link=link&link__icontains' \
                        '=link&ordering=message_type&_=1684210238128'
        response = self.api_client.get(reverse('api-notificationtable-list') +
                                       search_script)
        self.client.logout()
        filtered_expected = 1
        total_expected = 3
        result = response.json()
        self.assertEqual(result['recordsFiltered'], filtered_expected)
        self.assertEqual(result['recordsTotal'], total_expected)

    def test_link_input_filter_returns_no_records(self):
        self.api_client.login(username='third_user', password='tuser123')
        search_script = '?offset=0&limit=10&draw=11&link=link&link__icontains' \
                        '=link&ordering=message_type&_=1684210238128'
        response = self.api_client.get(reverse('api-notificationtable-list') +
                                       search_script)
        self.client.logout()
        filtered_expected = 0
        total_expected = 3
        result = response.json()
        self.assertEqual(result['recordsFiltered'], filtered_expected)
        self.assertEqual(result['recordsTotal'], total_expected)

    def test_state_input_filter_returns_one_record(self):
        user_notification = Notification.objects.filter(user=self.third_user)[0]
        user_notification.state = 'hide'
        user_notification.save()

        self.api_client.login(username='third_user', password='tuser123')
        search_script = '?offset=0&limit=10&draw=4&state=hid&state' \
                        '__icontains=hid&ordering=message_type&_=1684210238121'
        response = self.api_client.get(reverse('api-notificationtable-list') +
                                       search_script)
        self.client.logout()
        filtered_expected = 1
        total_expected = 3
        result = response.json()
        self.assertEqual(result['recordsFiltered'], filtered_expected)
        self.assertEqual(result['recordsTotal'], total_expected)

    def test_state_input_filter_returns_no_records(self):
        self.api_client.login(username='third_user', password='tuser123')
        search_script = '?offset=0&limit=10&draw=4&state=hid&state' \
                        '__icontains=hid&ordering=message_type&_=1684210238121'
        response = self.api_client.get(reverse('api-notificationtable-list') +
                                       search_script)
        self.client.logout()
        filtered_expected = 0
        total_expected = 3
        result = response.json()
        self.assertEqual(result['recordsFiltered'], filtered_expected)
        self.assertEqual(result['recordsTotal'], total_expected)

    def test_requesting_notifications_from_another_user(self):
        self.api_client.login(username='first_user', password='fuser123')
        search_script = '?offset=0&limit=10&draw=4&user__username=second_user&user' \
                        '__username__icontains=second_user&ordering=message_type' \
                        '&_=1684210238121'
        response = self.api_client.get(reverse('api-notificationtable-list') +
                                       search_script)
        self.client.logout()
        filtered_expected = 1
        total_expected = 1
        result = response.json()
        self.assertEqual(result['recordsFiltered'], filtered_expected)
        self.assertEqual(result['recordsTotal'], total_expected)
