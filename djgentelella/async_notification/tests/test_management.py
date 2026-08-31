from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from djgentelella.async_notification.tests import AsyncNotificationTestBase
from djgentelella.async_notification.models import (
    EmailNotification, NewsLetter, NewsLetterTask
)
from djgentelella.async_notification.sending import do_send_notification


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
        notification = EmailNotification.objects.create(
            subject='Not Enqueued',
            message='<p>Hi</p>',
            recipients='skip@example.com',
            enqueued=False,
        )
        # The signal will have already sent this one; reset status to pending
        # to simulate the scenario where it wasn't sent by signal either
        EmailNotification.objects.filter(pk=notification.pk).update(
            status='pending')
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

    def test_reaper_recovers_stuck_sending(self):
        """A notification stranded in 'sending' by a dead worker is reset to
        pending by the reaper and then sent in the same run."""
        n = EmailNotification.objects.create(
            subject='Stuck', message='<p>x</p>', recipients=['a@b.com'],
            status='sending')
        stale = timezone.now() - timedelta(hours=1)
        EmailNotification.objects.filter(pk=n.pk).update(updated_at=stale)
        call_command('process_notifications')
        n.refresh_from_db()
        self.assertEqual(n.status, 'sent')
        self.assertEqual(len(mail.outbox), 1)

    def test_reaper_leaves_fresh_sending_alone(self):
        """A recently-updated 'sending' row (an active worker) is not reaped."""
        n = EmailNotification.objects.create(
            subject='Active', message='<p>x</p>', recipients=['a@b.com'],
            status='sending')
        call_command('process_notifications')
        n.refresh_from_db()
        self.assertEqual(n.status, 'sending')
        self.assertEqual(len(mail.outbox), 0)


class ClaimIdempotencyTest(AsyncNotificationTestBase):
    """The atomic claim prevents a second concurrent send of the same row."""

    def test_send_skips_row_already_sending(self):
        n = EmailNotification.objects.create(
            subject='Racing', message='<p>x</p>', recipients=['a@b.com'],
            status='sending')
        do_send_notification(n.pk)   # another worker already has it
        n.refresh_from_db()
        self.assertEqual(n.status, 'sending')
        self.assertEqual(len(mail.outbox), 0)
