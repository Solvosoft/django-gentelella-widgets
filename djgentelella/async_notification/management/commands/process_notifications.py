"""
Management command to process pending email notifications and
due newsletter tasks. Designed for cron-based deployments without Celery.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from djgentelella.async_notification.models import (
    AttachedFile, EmailNotification, NewsLetterTask
)
from djgentelella.async_notification.sending import (
    do_send_notification, do_send_newsletter
)


class Command(BaseCommand):
    help = 'Process pending email notifications and due newsletter tasks.'

    def handle(self, *args, **options):
        sent_count = 0
        failed_count = 0

        # Process pending enqueued notifications
        while True:
            with transaction.atomic():
                notification = (
                    EmailNotification.objects
                    .select_for_update(skip_locked=True)
                    .filter(status='pending', enqueued=True)
                    .first()
                )
                if notification is None:
                    break
                notification.status = 'sending'
                notification.save(update_fields=['status'])

            try:
                do_send_notification(notification.pk)
                sent_count += 1
            except Exception as e:
                failed_count += 1
                self.stderr.write(
                    f'Error processing notification {notification.pk}: {e}')

        # Process due newsletter tasks
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
                task.status = 'sending'
                task.save(update_fields=['status'])

            try:
                do_send_newsletter(task.pk)
                sent_count += 1
            except Exception as e:
                failed_count += 1
                self.stderr.write(
                    f'Error processing newsletter task {task.pk}: {e}')

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
