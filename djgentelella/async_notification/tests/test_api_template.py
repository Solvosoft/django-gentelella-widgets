from django.urls import reverse

from djgentelella.async_notification.tests import AsyncNotificationAPITestBase
from djgentelella.async_notification.models import EmailTemplate


class EmailTemplateAPITest(AsyncNotificationAPITestBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from django.contrib.auth.models import Permission
        cls.superuser.user_permissions.set(Permission.objects.all())

    def test_list(self):
        EmailTemplate.objects.create(
            code='test-tpl', subject='S', message='M')
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-emailtemplate-list')
        response = self.get_datatable_response(url, self.superuser)
        self.assert_datatable_response(response, expected_count=1)

    def test_create(self):
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-emailtemplate-list')
        data = {
            'code': 'new-template',
            'subject': 'New Subject',
            'message': '<p>Content</p>',
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            EmailTemplate.objects.filter(code='new-template').exists())

    def test_update(self):
        template = EmailTemplate.objects.create(
            code='upd-tpl', subject='Old', message='M')
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-emailtemplate-detail',
                      args=[template.pk])
        response = self.client.put(url, {
            'code': 'upd-tpl',
            'subject': 'Updated',
            'message': 'M2',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        template.refresh_from_db()
        self.assertEqual(template.subject, 'Updated')

    def test_delete(self):
        template = EmailTemplate.objects.create(
            code='del-tpl', subject='S', message='M')
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-emailtemplate-detail',
                      args=[template.pk])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)

    def test_search(self):
        EmailTemplate.objects.create(
            code='search-me', subject='Found', message='M')
        EmailTemplate.objects.create(
            code='other', subject='Other', message='M')
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-emailtemplate-list')
        response = self.get_datatable_response(
            url, self.superuser, {'search': 'search-me'})
        self.assert_datatable_response(response, expected_count=1)

    def test_get_values_for_update(self):
        template = EmailTemplate.objects.create(
            code='get-val', subject='S', message='M')
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-emailtemplate-get-values-for-update',
                      args=[template.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 'get-val')
