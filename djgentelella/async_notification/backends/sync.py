"""
Synchronous backend — sends emails directly in the current process.
"""

from djgentelella.async_notification.backends.base import NotificationBackend
from djgentelella.async_notification.models import NewsLetterTask
from djgentelella.async_notification.sending import (
    do_send_notification, do_send_newsletter
)


class SyncBackend(NotificationBackend):
    """Sends notifications synchronously in the current thread."""

    def send(self, notification_pk):
        do_send_notification(notification_pk)

    def schedule(self, newsletter_task_pk):
        """Mark the task as scheduled (actual send handled by management command)."""
        try:
            task = NewsLetterTask.objects.get(pk=newsletter_task_pk)
            task.status = 'scheduled'
            task.save(update_fields=['status'])
        except NewsLetterTask.DoesNotExist:
            pass

    def revoke(self, newsletter_task_pk):
        """Mark the task as revoked."""
        try:
            task = NewsLetterTask.objects.get(pk=newsletter_task_pk)
            if task.status in ('pending', 'scheduled'):
                task.status = 'revoked'
                task.save(update_fields=['status'])
        except NewsLetterTask.DoesNotExist:
            pass
