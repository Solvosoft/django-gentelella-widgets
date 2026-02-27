from django.test import TestCase
from django.urls import reverse

from djgentelella.async_notification.tests import AsyncNotificationTestBase


class HTMLViewsTest(AsyncNotificationTestBase):

    def test_email_notification_view_authenticated(self):
        self.client.force_login(self.user)
        url = reverse('async_notification:email_notification')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_email_template_view_authenticated(self):
        self.client.force_login(self.user)
        url = reverse('async_notification:email_template')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_newsletter_view_authenticated(self):
        self.client.force_login(self.user)
        url = reverse('async_notification:newsletter')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_newsletter_template_view_authenticated(self):
        self.client.force_login(self.user)
        url = reverse('async_notification:newsletter_template')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_newsletter_task_view_authenticated(self):
        self.client.force_login(self.user)
        url = reverse('async_notification:newsletter_task')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_login_required_redirects(self):
        """All views should redirect to login when not authenticated."""
        urls = [
            reverse('async_notification:email_notification'),
            reverse('async_notification:email_template'),
            reverse('async_notification:newsletter'),
            reverse('async_notification:newsletter_template'),
            reverse('async_notification:newsletter_task'),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, f'{url} should redirect')

    def test_form_prefix_email_notification(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('async_notification:email_notification'))
        form = response.context['form']
        self.assertEqual(form.prefix, 'emailnotification')

    def test_form_prefix_email_template(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('async_notification:email_template'))
        form = response.context['form']
        self.assertEqual(form.prefix, 'emailtemplate')


class AuxiliaryEndpointsTest(AsyncNotificationTestBase):

    def test_autocomplete_requires_login(self):
        url = reverse('async_notification:email_autocomplete')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_autocomplete_short_query(self):
        self.client.force_login(self.user)
        url = reverse('async_notification:email_autocomplete')
        response = self.client.get(url, {'q': 'a'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'')

    def test_autocomplete_search(self):
        self.client.force_login(self.user)
        url = reverse('async_notification:email_autocomplete')
        response = self.client.get(url, {'q': 'testuser'})
        self.assertEqual(response.status_code, 200)

    def test_model_fields_no_code(self):
        self.client.force_login(self.user)
        url = reverse('async_notification:model_fields')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)

    def test_model_fields_unknown_code(self):
        self.client.force_login(self.user)
        url = reverse('async_notification:model_fields')
        response = self.client.get(url, {'code': 'unknown'})
        self.assertEqual(response.status_code, 404)

    def test_preview_template_get_not_allowed(self):
        self.client.force_login(self.user)
        url = reverse('async_notification:preview_template')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
