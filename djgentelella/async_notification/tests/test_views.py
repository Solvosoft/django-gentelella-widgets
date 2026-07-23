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
        """Create/update modals use distinct prefixes to avoid id collisions."""
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('async_notification:email_notification'))
        self.assertEqual(response.context['create_form'].prefix, 'create')
        self.assertEqual(response.context['update_form'].prefix, 'update')

    def test_form_prefix_email_template(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('async_notification:email_template'))
        self.assertEqual(response.context['create_form'].prefix, 'create')
        self.assertEqual(response.context['update_form'].prefix, 'update')


class AuxiliaryEndpointsTest(AsyncNotificationTestBase):
    # The compose helpers require an email-authoring permission; the superuser
    # holds every permission. See PermissionRequiredTest for the denial path.

    def test_autocomplete_requires_login(self):
        url = reverse('async_notification:email_autocomplete')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_autocomplete_short_query(self):
        self.client.force_login(self.superuser)
        url = reverse('async_notification:email_autocomplete')
        response = self.client.get(url, {'q': 'a'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'')

    def test_autocomplete_search(self):
        self.client.force_login(self.superuser)
        url = reverse('async_notification:email_autocomplete')
        response = self.client.get(url, {'q': 'testuser'})
        self.assertEqual(response.status_code, 200)

    def test_model_fields_no_code(self):
        self.client.force_login(self.superuser)
        url = reverse('async_notification:model_fields')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)

    def test_model_fields_unknown_code(self):
        self.client.force_login(self.superuser)
        url = reverse('async_notification:model_fields')
        response = self.client.get(url, {'code': 'unknown'})
        self.assertEqual(response.status_code, 404)

    def test_preview_template_get_not_allowed(self):
        self.client.force_login(self.superuser)
        url = reverse('async_notification:preview_template')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)


class PermissionRequiredTest(AsyncNotificationTestBase):
    """A logged-in user without any email-authoring/view permission must be
    denied the compose helpers (no email enumeration, no uploads, no IDOR)."""

    AUTHORING_ENDPOINTS = [
        ('async_notification:email_autocomplete', 'get'),
        ('async_notification:async_upload_image', 'post'),
        ('async_notification:async_upload_video', 'post'),
        ('async_notification:reassociate_files', 'post'),
        ('async_notification:preview_template', 'post'),
        ('async_notification:newsletter_recipients_preview', 'post'),
    ]

    def test_authoring_helpers_denied_without_perm(self):
        self.client.force_login(self.noperms_user)
        for name, method in self.AUTHORING_ENDPOINTS:
            response = getattr(self.client, method)(reverse(name))
            self.assertEqual(response.status_code, 403,
                             f'{name} should be 403 for a user without perms')

    def test_preview_file_denied_without_perm(self):
        from django.contrib.contenttypes.models import ContentType
        from django.core.files.uploadedfile import SimpleUploadedFile
        from djgentelella.async_notification.models import (
            AttachedFile, EmailNotification,
        )
        att = AttachedFile.objects.create(
            content_type=ContentType.objects.get_for_model(EmailNotification),
            object_id=0,
            file=SimpleUploadedFile('x.png', b'data', content_type='image/png'),
        )
        self.client.force_login(self.noperms_user)
        response = self.client.get(
            reverse('async_notification:preview_file', args=[att.pk]))
        self.assertEqual(response.status_code, 403)
