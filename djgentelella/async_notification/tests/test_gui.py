"""Tests for the GUI-supporting endpoints and viewset actions."""

from django.core import mail
from django.urls import reverse
from django.utils import timezone

from djgentelella.async_notification.tests import (
    AsyncNotificationTestBase, AsyncNotificationAPITestBase,
)
from djgentelella.async_notification.models import (
    EmailNotification, NewsLetter, NewsLetterTemplate, NewsLetterTask,
)
from djgentelella.async_notification.interfaces import (
    register_news_basemodel, clear_basemodels,
)
from djgentelella.async_notification.sending import do_send_newsletter
from djgentelella.async_notification.tests.test_interfaces import UserInterface


class NewsletterBaseTemplateSendTest(AsyncNotificationTestBase):

    def test_send_wraps_message_in_base_template(self):
        newsletter = NewsLetter.objects.create(
            subject='Wrapped news', message='<p>Body</p>',
            recipients=['a@b.com'], base_template='default')
        task = NewsLetterTask.objects.create(
            newsletter=newsletter, send_date=timezone.now(), status='pending')
        do_send_newsletter(task.pk)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn('async-email-body', body)
        self.assertIn('Body', body)


class TemplatePreviewActionTest(AsyncNotificationAPITestBase):

    def test_newsletter_template_preview(self):
        template = NewsLetterTemplate.objects.create(
            title='T', slug='t', message='<p>Hi</p>', base_template='default')
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-newslettertemplate-preview',
                      args=[template.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['message'], '<p>Hi</p>')
        self.assertEqual(data['base_template'], 'default')

    def test_newsletter_preview_returns_base_template(self):
        newsletter = NewsLetter.objects.create(
            subject='S', message='<p>M</p>', recipients=['a@b.com'],
            base_template='default')
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-newsletter-preview',
                      args=[newsletter.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['base_template'], 'default')


class EmailNotificationPreviewActionTest(AsyncNotificationAPITestBase):

    def test_preview_returns_body_and_status(self):
        notification = EmailNotification.objects.create(
            subject='Seen', message='<p>Body</p>', recipients=['a@b.com'],
            status='sent', recipients_raw='a@b.com')
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-emailnotification-preview',
                      args=[notification.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['message'], '<p>Body</p>')
        self.assertEqual(data['status'], 'sent')
        self.assertEqual(data['recipients_raw'], 'a@b.com')


class TaskSendNowActionTest(AsyncNotificationAPITestBase):

    def test_send_now_sends_immediately(self):
        newsletter = NewsLetter.objects.create(
            subject='Now', message='<p>M</p>', recipients=['a@b.com'])
        task = NewsLetterTask.objects.create(
            newsletter=newsletter, send_date=timezone.now(), status='pending')
        self.client.force_login(self.superuser)
        url = reverse('async_notification:api-newslettertask-send-now',
                      args=[task.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['result'])
        task.refresh_from_db()
        self.assertEqual(task.status, 'sent')
        self.assertEqual(len(mail.outbox), 1)


class RecipientsPreviewEndpointTest(AsyncNotificationTestBase):

    def tearDown(self):
        clear_basemodels()

    def test_merges_free_text_and_interface(self):
        register_news_basemodel('users', 'Users', UserInterface)
        template = NewsLetterTemplate.objects.create(
            title='T', slug='t', message='M', model_base='users')
        self.client.force_login(self.superuser)
        url = reverse('async_notification:newsletter_recipients_preview')
        response = self.client.post(url, {
            'template': template.pk,
            'recipients': 'extra@x.com',
            'filters_querystring': 'excludeemail=admin@example.com',
        })
        self.assertEqual(response.status_code, 200)
        emails = response.json()['recipients']
        self.assertIn('extra@x.com', emails)
        self.assertIn('testuser@example.com', emails)
        self.assertNotIn('admin@example.com', emails)

    def test_requires_login(self):
        url = reverse('async_notification:newsletter_recipients_preview')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
