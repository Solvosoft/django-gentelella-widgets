from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from djgentelella.async_notification.tests import AsyncNotificationTestBase
from djgentelella.async_notification.models import (
    EmailNotification, NewsLetter, NewsLetterTask
)


class ProcessNotificationsCommandTest(AsyncNotificationTestBase):

    def test_pending_enqueued_processed(self):
        notification = EmailNotification.objects.create(
            subject='Command Test',
            message='<p>Hello</p>',
            recipients='cmd@example.com',
            enqueued=True,
        )
        call_command('process_notifications')
        notification.refresh_from_db()
        self.assertEqual(notification.status, 'sent')
        self.assertTrue(notification.sent)
        self.assertEqual(len(mail.outbox), 1)

    def test_non_enqueued_ignored(self):
        """Notifications with enqueued=False should not be processed by command."""
        from unittest.mock import patch
        from djgentelella.async_notification.backends.sync import SyncBackend
        sync = SyncBackend()
        with patch('djgentelella.async_notification.backends.get_backend',
                   return_value=sync):
            notification = EmailNotification.objects.create(
                subject='Not Enqueued',
                message='<p>Hi</p>',
                recipients='skip@example.com',
                enqueued=False,
            )
        # Reset status to pending to simulate the scenario where it wasn't sent by signal
        EmailNotification.objects.filter(pk=notification.pk).update(
            status='pending', sent=False)
        mail.outbox.clear()
        call_command('process_notifications')
        notification.refresh_from_db()
        # Should still be pending since enqueued=False
        self.assertEqual(notification.status, 'pending')

    def test_already_sent_ignored(self):
        EmailNotification.objects.create(
            subject='Already Sent',
            message='<p>Hi</p>',
            recipients='done@example.com',
            status='sent',
            sent=True,
            enqueued=True,
        )
        call_command('process_notifications')
        self.assertEqual(len(mail.outbox), 0)

    def test_due_newsletter_task_processed(self):
        newsletter = NewsLetter.objects.create(
            subject='Due Newsletter',
            message='<p>News</p>',
            recipients='news@example.com',
        )
        task = NewsLetterTask.objects.create(
            newsletter=newsletter,
            send_date=timezone.now() - timedelta(minutes=5),
            status='scheduled',
        )
        call_command('process_notifications')
        task.refresh_from_db()
        self.assertEqual(task.status, 'sent')
        self.assertEqual(len(mail.outbox), 1)

    def test_future_task_ignored(self):
        newsletter = NewsLetter.objects.create(
            subject='Future Newsletter',
            message='<p>Future</p>',
            recipients='future@example.com',
        )
        task = NewsLetterTask.objects.create(
            newsletter=newsletter,
            send_date=timezone.now() + timedelta(hours=1),
            status='scheduled',
        )
        call_command('process_notifications')
        task.refresh_from_db()
        self.assertEqual(task.status, 'scheduled')
        self.assertEqual(len(mail.outbox), 0)

    def test_multiple_notifications(self):
        for i in range(3):
            EmailNotification.objects.create(
                subject=f'Multi {i}',
                message='<p>Hi</p>',
                recipients=f'multi{i}@example.com',
                enqueued=True,
            )
        call_command('process_notifications')
        self.assertEqual(len(mail.outbox), 3)
        for n in EmailNotification.objects.all():
            self.assertEqual(n.status, 'sent')
