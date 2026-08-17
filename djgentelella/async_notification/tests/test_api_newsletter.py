import base64

from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import formats, timezone

from djgentelella.async_notification.tests import AsyncNotificationAPITestBase
from djgentelella.async_notification.models import (
    NewsLetterTemplate, NewsLetter, NewsLetterTask
)
from djgentelella.async_notification.backends import reset_backend


class NewsLetterAPITest(AsyncNotificationAPITestBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.superuser.user_permissions.set(Permission.objects.all())
        cls.template = NewsLetterTemplate.objects.create(
            title='Test Template', slug='test-tpl', message='M')

    def test_list(self):
        NewsLetter.objects.create(
            subject='NL Test', message='M', recipients='a@b.com',
            template=self.template)
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-newsletter-list')
        response = self.get_datatable_response(url, self.superuser)
        self.assert_datatable_response(response, expected_count=1)

    def test_create(self):
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-newsletter-list')
        data = {
            'template': self.template.pk,
            'subject': 'API Newsletter',
            'message': '<p>News</p>',
            'recipients': ['news@example.com'],
        }
        response = self.client.post(
            url, data, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            NewsLetter.objects.filter(subject='API Newsletter').exists())

    def test_create_with_attached_file(self):
        """The compose modal sends files as base64 JSON, not multipart."""
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-newsletter-list')
        content = base64.b64encode(b'fake odt bytes').decode()
        data = {
            'template': self.template.pk,
            'subject': 'With Attachment',
            'message': '<p>News</p>',
            'recipients': ['news@example.com'],
            'attached_file': [{'name': 'report.odt', 'value': content}],
        }
        response = self.client.post(
            url, data, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        newsletter = NewsLetter.objects.get(subject='With Attachment')
        self.assertTrue(newsletter.attached_file.name.endswith('.odt'))
        self.assertEqual(newsletter.attached_file.read(), b'fake odt bytes')

    def test_get_values_for_update(self):
        """Regression: base_template/template used to crash this endpoint.

        A plain GTS2SerializerBase on a CharField (base_template) tried
        ``getattr(value, 'pk')`` on a plain string and raised AttributeError.
        """
        newsletter = NewsLetter.objects.create(
            subject='NL Edit', message='M', recipients='a@b.com',
            template=self.template, base_template='executive')
        self.client.force_login(self.superuser)
        url = reverse(
            'async_notification:api-newsletter-get-values-for-update',
            args=[newsletter.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        # Select2-shaped {id, text} for both the FK and the choice field.
        self.assertEqual(data['template']['id'], self.template.pk)
        self.assertEqual(data['template']['text'], self.template.title)
        self.assertEqual(data['base_template']['id'], 'executive')

    def test_preview_recipients(self):
        newsletter = NewsLetter.objects.create(
            subject='Preview R', message='M',
            recipients='a@b.com, c@d.com')
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-newsletter-preview-recipients',
                      args=[newsletter.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 2)


class NewsLetterTaskAPITest(AsyncNotificationAPITestBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.superuser.user_permissions.set(Permission.objects.all())
        cls.newsletter = NewsLetter.objects.create(
            subject='Task NL', message='M', recipients='a@b.com')

    def setUp(self):
        reset_backend()

    def tearDown(self):
        reset_backend()

    def test_create_schedules_task(self):
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-newslettertask-list')
        fmt = formats.get_format('DATETIME_INPUT_FORMATS')[0]
        send_date = timezone.now().strftime(fmt)
        data = {
            'newsletter': self.newsletter.pk,
            'send_date': send_date,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 201)
        task = NewsLetterTask.objects.latest('pk')
        self.assertEqual(task.status, 'scheduled')

    def test_destroy_revokes_task(self):
        task = NewsLetterTask.objects.create(
            newsletter=self.newsletter,
            send_date=timezone.now(),
            status='scheduled',
        )
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-newslettertask-detail',
                      args=[task.pk])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)

    def test_list(self):
        NewsLetterTask.objects.create(
            newsletter=self.newsletter,
            send_date=timezone.now(),
        )
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-newslettertask-list')
        response = self.get_datatable_response(url, self.superuser)
        self.assert_datatable_response(response, expected_count=1)
