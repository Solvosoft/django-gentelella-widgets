from django.core import mail
from django.urls import reverse

from djgentelella.async_notification.tests import AsyncNotificationAPITestBase
from djgentelella.async_notification.models import EmailNotification


class EmailNotificationAPITest(AsyncNotificationAPITestBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Give superuser all permissions
        from django.contrib.auth.models import Permission
        cls.superuser.user_permissions.set(Permission.objects.all())

    def test_list(self):
        EmailNotification.objects.create(
            subject='Test', message='M', recipients='a@b.com')
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-emailnotification-list')
        response = self.get_datatable_response(url, self.superuser)
        self.assert_datatable_response(response, expected_count=1)

    def test_create(self):
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-emailnotification-list')
        data = {
            'subject': 'API Created',
            'message': '<p>Hello</p>',
            'recipients': 'api@example.com',
            'enqueued': True,
            'send_individually': False,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            EmailNotification.objects.filter(subject='API Created').exists())

    def test_retrieve(self):
        notification = EmailNotification.objects.create(
            subject='Detail', message='M', recipients='a@b.com')
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-emailnotification-detail',
                      args=[notification.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['subject'], 'Detail')

    def test_update(self):
        notification = EmailNotification.objects.create(
            subject='Old', message='M', recipients='a@b.com')
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-emailnotification-detail',
                      args=[notification.pk])
        response = self.client.put(url, {
            'subject': 'Updated',
            'message': 'M2',
            'recipients': 'a@b.com',
            'enqueued': True,
            'send_individually': False,
        }, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        notification.refresh_from_db()
        self.assertEqual(notification.subject, 'Updated')

    def test_delete(self):
        notification = EmailNotification.objects.create(
            subject='Delete Me', message='M', recipients='a@b.com')
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-emailnotification-detail',
                      args=[notification.pk])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(EmailNotification.objects.filter(
            pk=notification.pk).exists())

    def test_send_email_action(self):
        notification = EmailNotification.objects.create(
            subject='Send Me', message='<p>Hi</p>', recipients='a@b.com')
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-emailnotification-send-email',
                      args=[notification.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['result'])
        self.assertEqual(len(mail.outbox), 1)

    def test_send_selected_action(self):
        n1 = EmailNotification.objects.create(
            subject='S1', message='M', recipients='a@b.com')
        n2 = EmailNotification.objects.create(
            subject='S2', message='M', recipients='c@d.com')
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-emailnotification-send-selected')
        response = self.client.post(url, {'pks': [n1.pk, n2.pk]},
                                     content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 2)

    def test_search(self):
        EmailNotification.objects.create(
            subject='FindMe', message='M', recipients='a@b.com')
        EmailNotification.objects.create(
            subject='Other', message='M', recipients='a@b.com')
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-emailnotification-list')
        response = self.get_datatable_response(
            url, self.superuser, {'search': 'FindMe'})
        self.assert_datatable_response(response, expected_count=1)

    def test_permission_denied(self):
        self.client.force_login(self.noperms_user)
        url = reverse('async_notification:api-emailnotification-list')
        response = self.client.get(url, {'draw': 1, 'limit': 10, 'offset': 0})
        self.assertEqual(response.status_code, 403)
