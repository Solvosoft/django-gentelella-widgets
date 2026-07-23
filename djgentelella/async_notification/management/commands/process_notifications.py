"""
Management command to process pending email notifications and
due newsletter tasks. Designed for cron-based deployments without Celery.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from djgentelella.async_notification.models import (
    AttachedFile, EmailNotification, NewsLetterTask
)
from djgentelella.async_notification.sending import (
    do_send_notification, do_send_newsletter
)
from djgentelella.async_notification.settings import (
    ASYNC_NOTIFICATION_RETRY_DELAY,
    ASYNC_NOTIFICATION_STUCK_MINUTES,
)


class Command(BaseCommand):
    help = 'Process pending email notifications and due newsletter tasks.'

    def _reap_stuck(self, now):
        """Reset rows stranded in 'sending' by a dead worker back to pending.

        A crash/OOM/redeploy between claiming a row ('sending') and finishing
        leaves it unreachable: the send loops only pick 'pending'/'queued'
        (and 'pending'/'scheduled') rows, so without this the send would stall
        forever. Re-attempts are safe because both send paths resume from
        ``sent_recipients`` and never re-send delivered addresses.
        """
        # ``updated_at`` advances with every per-batch progress save, so an
        # actively-sending long job is not wrongly reaped; only a row with no
        # save for the whole window (a dead worker) is reset.
        stuck_before = now - timedelta(minutes=ASYNC_NOTIFICATION_STUCK_MINUTES)
        reaped = EmailNotification.objects.filter(
            status='sending', updated_at__lt=stuck_before,
        ).update(status='pending')
        reaped += NewsLetterTask.objects.filter(
            status='sending', updated_at__lt=stuck_before,
        ).update(status='pending')
        return reaped

    def handle(self, *args, **options):
        sent_count = 0
        failed_count = 0
        now = timezone.now()

        reaped = self._reap_stuck(now)

        # Notifications never attempted, or whose backoff window has elapsed.
        # The base retry delay gates re-attempts here (the exact exponential
        # backoff applies on the Celery path via apply_async countdown).
        retry_ready = Q(last_attempt__isnull=True) | Q(
            last_attempt__lte=now - timedelta(
                seconds=ASYNC_NOTIFICATION_RETRY_DELAY))

        # Process pending/queued enqueued notifications. The row is claimed
        # atomically inside do_send_notification (status -> 'sending'), so the
        # loop just picks candidate pks; retry_ready/last_attempt gates a
        # just-attempted row out of re-selection within the same run.
        while True:
            with transaction.atomic():
                notification = (
                    EmailNotification.objects
                    .select_for_update(skip_locked=True)
                    .filter(retry_ready, status__in=('pending', 'queued'),
                            enqueued=True)
                    .first()
                )
                if notification is None:
                    break
                pk = notification.pk

            try:
                do_send_notification(pk)
                sent_count += 1
            except Exception as e:
                failed_count += 1
                self.stderr.write(
                    f'Error processing notification {pk}: {e}')

        # Process due newsletter tasks (claimed atomically in do_send_newsletter)
        now = timezone.now()
        while True:
            with transaction.atomic():
                task = (
                    NewsLetterTask.objects
                    .select_for_update(skip_locked=True)
                    .filter(
                        status__in=('pending', 'scheduled'),
                        send_date__lte=now,
                    )
                    .first()
                )
                if task is None:
                    break
                task_pk = task.pk

            try:
                do_send_newsletter(task_pk)
                sent_count += 1
            except Exception as e:
                failed_count += 1
                self.stderr.write(
                    f'Error processing newsletter task {task_pk}: {e}')

        # Cleanup orphaned attached files (object_id=0, older than 24h)
        cutoff = now - timedelta(hours=24)
        orphans = AttachedFile.objects.filter(
            object_id=0, created_at__lt=cutoff)
        orphan_count = orphans.count()
        for orphan in orphans:
            orphan.file.delete(save=False)
        orphans.delete()

        self.stdout.write(
            f'Processed: {sent_count} sent, {failed_count} failed, '
            f'{orphan_count} orphan files cleaned.')
