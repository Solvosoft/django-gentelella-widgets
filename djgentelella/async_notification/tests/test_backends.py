from django.core import mail
from django.test import override_settings
from django.utils import timezone

from djgentelella.async_notification.tests import AsyncNotificationTestBase
from djgentelella.async_notification.models import (
    EmailNotification, NewsLetter, NewsLetterTask
)
from djgentelella.async_notification.backends import (
    get_backend, reset_backend
)
from djgentelella.async_notification.backends.sync import SyncBackend


class SyncBackendTest(AsyncNotificationTestBase):

    def setUp(self):
        reset_backend()

    def tearDown(self):
        reset_backend()

    def test_sync_send(self):
        backend = SyncBackend()
        notification = EmailNotification.objects.create(
            subject='Sync Test',
            message='<p>Hello</p>',
            recipients='sync@example.com',
        )
        backend.send(notification.pk)
        notification.refresh_from_db()
        self.assertEqual(notification.status, 'sent')
        self.assertEqual(len(mail.outbox), 1)

    def test_sync_schedule(self):
        newsletter = NewsLetter.objects.create(
            subject='NL', message='M', recipients='a@b.com')
        task = NewsLetterTask.objects.create(
            newsletter=newsletter,
            send_date=timezone.now(),
        )
        backend = SyncBackend()
        backend.schedule(task.pk)
        task.refresh_from_db()
        self.assertEqual(task.status, 'scheduled')

    def test_sync_revoke(self):
        newsletter = NewsLetter.objects.create(
            subject='NL', message='M', recipients='a@b.com')
        task = NewsLetterTask.objects.create(
            newsletter=newsletter,
            send_date=timezone.now(),
            status='scheduled',
        )
        backend = SyncBackend()
        backend.revoke(task.pk)
        task.refresh_from_db()
        self.assertEqual(task.status, 'revoked')

    def test_sync_revoke_only_pending_or_scheduled(self):
        newsletter = NewsLetter.objects.create(
            subject='NL', message='M', recipients='a@b.com')
        task = NewsLetterTask.objects.create(
            newsletter=newsletter,
            send_date=timezone.now(),
            status='sent',
        )
        backend = SyncBackend()
        backend.revoke(task.pk)
        task.refresh_from_db()
        self.assertEqual(task.status, 'sent')  # Not changed


class GetBackendTest(AsyncNotificationTestBase):

    def setUp(self):
        reset_backend()

    def tearDown(self):
        reset_backend()

    def test_default_backend_is_sync(self):
        """Without Celery configured, default backend should be SyncBackend."""
        backend = get_backend()
        self.assertIsInstance(backend, SyncBackend)

    def test_singleton(self):
        backend1 = get_backend()
        backend2 = get_backend()
        self.assertIs(backend1, backend2)

    def test_reset_backend(self):
        backend1 = get_backend()
        reset_backend()
        backend2 = get_backend()
        self.assertIsNot(backend1, backend2)

    @override_settings(
        ASYNC_NOTIFICATION_BACKEND='djgentelella.async_notification.backends.sync.SyncBackend')
    def test_explicit_backend_setting(self):
        reset_backend()
        # Need to reimport settings since it's cached at module level
        from djgentelella.async_notification import backends
        old_val = backends.ASYNC_NOTIFICATION_BACKEND
        backends.ASYNC_NOTIFICATION_BACKEND = \
            'djgentelella.async_notification.backends.sync.SyncBackend'
        try:
            backend = get_backend()
            self.assertIsInstance(backend, SyncBackend)
        finally:
            backends.ASYNC_NOTIFICATION_BACKEND = old_val


class SignalDispatchTest(AsyncNotificationTestBase):

    def setUp(self):
        reset_backend()

    def tearDown(self):
        reset_backend()

    def test_immediate_send_via_signal(self):
        """Creating notification with enqueued=False triggers immediate send."""
        notification = EmailNotification.objects.create(
            subject='Signal Test',
            message='<p>Immediate</p>',
            recipients='signal@example.com',
            enqueued=False,
        )
        notification.refresh_from_db()
        self.assertEqual(notification.status, 'sent')
        self.assertTrue(notification.sent)
        self.assertEqual(len(mail.outbox), 1)

    def test_enqueued_does_not_trigger_signal(self):
        """Creating notification with enqueued=True does not send immediately."""
        notification = EmailNotification.objects.create(
            subject='Queued',
            message='<p>Later</p>',
            recipients='queued@example.com',
            enqueued=True,
        )
        notification.refresh_from_db()
        self.assertEqual(notification.status, 'pending')
        self.assertEqual(len(mail.outbox), 0)
