"""Tests for deliverability/compliance features.

One-click unsubscribe (RFC 8058), suppression list, opt-in, multipart
plain-text alternative, bulk headers, and the suppression webhook.
"""

from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from django.urls import reverse

from djgentelella.async_notification.tests import AsyncNotificationTestBase
from djgentelella.async_notification.models import (
    EmailNotification, EmailSuppression, EmailConsent,
)
from djgentelella.async_notification.sending import do_send_notification
from djgentelella.async_notification.unsubscribe import make_token, read_token

BASE = 'djgentelella.async_notification.unsubscribe.ASYNC_NOTIFICATION_BASE_URL'
SECRET = ('djgentelella.async_notification.settings.'
          'ASYNC_NOTIFICATION_WEBHOOK_SECRET')


class MultipartAndHeadersTest(AsyncNotificationTestBase):

    def test_multipart_plain_text_alternative(self):
        n = EmailNotification.objects.create(
            subject='S', message='<p>Hello <b>world</b></p>',
            recipients=['a@b.com'])
        do_send_notification(n.pk)
        msg = mail.outbox[0]
        # text/plain body + text/html alternative
        self.assertIn('Hello world', msg.body)
        self.assertEqual(msg.alternatives[0][1], 'text/html')
        self.assertIn('<b>world</b>', msg.alternatives[0][0])

    @patch(BASE, 'https://mail.example.com')
    def test_promotional_has_one_click_unsubscribe_headers(self):
        n = EmailNotification.objects.create(
            subject='Promo', message='<p>Buy</p>',
            recipients=['x@b.com', 'y@b.com'], is_promotional=True)
        do_send_notification(n.pk)
        # one message per recipient
        self.assertEqual(len(mail.outbox), 2)
        msg = mail.outbox[0]
        self.assertIn('List-Unsubscribe', msg.extra_headers)
        self.assertIn('https://mail.example.com/', msg.extra_headers[
            'List-Unsubscribe'])
        self.assertEqual(msg.extra_headers['List-Unsubscribe-Post'],
                         'List-Unsubscribe=One-Click')
        self.assertEqual(msg.extra_headers['Precedence'], 'bulk')

    def test_transactional_has_no_unsubscribe_headers(self):
        n = EmailNotification.objects.create(
            subject='Receipt', message='<p>Thanks</p>',
            recipients=['a@b.com'])   # is_promotional defaults to False
        do_send_notification(n.pk)
        self.assertNotIn('List-Unsubscribe', mail.outbox[0].extra_headers)


class SuppressionTest(AsyncNotificationTestBase):

    def test_promotional_skips_suppressed(self):
        EmailSuppression.objects.create(email='bad@b.com', reason='complaint')
        n = EmailNotification.objects.create(
            subject='Promo', message='<p>x</p>',
            recipients=['good@b.com', 'bad@b.com'], is_promotional=True)
        do_send_notification(n.pk)
        delivered = [a for m in mail.outbox for a in m.to]
        self.assertIn('good@b.com', delivered)
        self.assertNotIn('bad@b.com', delivered)

    def test_suppression_match_is_case_insensitive(self):
        # Unsubscribed as mixed-case; a later send resolves the same address
        # in lower case and must still be skipped.
        EmailSuppression.objects.create(email='Bad@B.com', reason='unsubscribe')
        n = EmailNotification.objects.create(
            subject='Promo', message='<p>x</p>',
            recipients=['good@b.com', 'bad@b.com'], is_promotional=True)
        do_send_notification(n.pk)
        delivered = [a for m in mail.outbox for a in m.to]
        self.assertIn('good@b.com', delivered)
        self.assertNotIn('bad@b.com', delivered)

    def test_suppression_email_stored_normalized(self):
        sup = EmailSuppression.objects.create(email='  MiXeD@Case.COM ')
        self.assertEqual(sup.email, 'mixed@case.com')

    def test_transactional_ignores_suppression(self):
        EmailSuppression.objects.create(email='bad@b.com', reason='unsubscribe')
        n = EmailNotification.objects.create(
            subject='Reset', message='<p>reset</p>',
            recipients=['bad@b.com'])   # transactional
        do_send_notification(n.pk)
        delivered = [a for m in mail.outbox for a in m.to]
        self.assertIn('bad@b.com', delivered)

    @override_settings()
    def test_optin_required_filters_non_consented(self):
        EmailConsent.objects.create(email='ok@b.com', granted=True)
        n = EmailNotification.objects.create(
            subject='Promo', message='<p>x</p>',
            recipients=['ok@b.com', 'no@b.com'], is_promotional=True)
        with patch('djgentelella.async_notification.sending.'
                   'ASYNC_NOTIFICATION_REQUIRE_OPTIN', True):
            do_send_notification(n.pk)
        delivered = [a for m in mail.outbox for a in m.to]
        self.assertEqual(delivered, ['ok@b.com'])


class UnsubscribeEndpointTest(AsyncNotificationTestBase):

    def test_token_round_trip(self):
        self.assertEqual(read_token(make_token('a@b.com')), 'a@b.com')

    def test_one_click_post_suppresses(self):
        token = make_token('unsub@b.com')
        url = reverse('async_notification:unsubscribe', args=[token])
        resp = self.client.post(url, {'List-Unsubscribe': 'One-Click'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            EmailSuppression.objects.filter(email='unsub@b.com').exists())

    def test_get_shows_confirmation_page(self):
        token = make_token('who@b.com')
        url = reverse('async_notification:unsubscribe', args=[token])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            EmailSuppression.objects.filter(email='who@b.com').exists())

    def test_invalid_token_rejected(self):
        url = reverse('async_notification:unsubscribe', args=['garbage'])
        self.assertEqual(self.client.post(url).status_code, 400)


class SuppressionWebhookTest(AsyncNotificationTestBase):

    def _url(self):
        return reverse('async_notification:suppression_webhook')

    def test_disabled_without_secret(self):
        with patch(SECRET, None):
            resp = self.client.post(
                self._url(), '{"email":"a@b.com"}',
                content_type='application/json')
        self.assertEqual(resp.status_code, 404)

    def test_wrong_secret_forbidden(self):
        with patch(SECRET, 's3cr3t'):
            resp = self.client.post(
                self._url(), '{"email":"a@b.com"}',
                content_type='application/json',
                HTTP_X_WEBHOOK_SECRET='nope')
        self.assertEqual(resp.status_code, 403)

    def test_valid_secret_suppresses(self):
        with patch(SECRET, 's3cr3t'):
            resp = self.client.post(
                self._url(), '{"email":"b@b.com","reason":"bounce"}',
                content_type='application/json',
                HTTP_X_WEBHOOK_SECRET='s3cr3t')
        self.assertEqual(resp.status_code, 200)
        sup = EmailSuppression.objects.get(email='b@b.com')
        self.assertEqual(sup.reason, 'bounce')

    def test_secret_in_query_string_rejected(self):
        # The secret must never travel in the query string (leaks to logs).
        with patch(SECRET, 's3cr3t'):
            resp = self.client.post(
                self._url() + '?secret=s3cr3t', '{"email":"c@b.com"}',
                content_type='application/json')
        self.assertEqual(resp.status_code, 403)
