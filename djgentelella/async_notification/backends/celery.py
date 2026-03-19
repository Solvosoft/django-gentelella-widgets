"""
Celery backend — dispatches notifications as Celery tasks.
"""

from djgentelella.async_notification.backends.base import NotificationBackend
from djgentelella.async_notification.models import NewsLetterTask


class CeleryBackend(NotificationBackend):
    """Sends notifications via Celery task queue."""

    def send(self, notification_pk):
        from djgentelella.async_notification.tasks import send_email_task
        send_email_task.delay(notification_pk)

    def schedule(self, newsletter_task_pk):
        from djgentelella.async_notification.tasks import send_newsletter_task
        try:
            task = NewsLetterTask.objects.get(pk=newsletter_task_pk)
        except NewsLetterTask.DoesNotExist:
            return

        result = send_newsletter_task.apply_async(
            args=[newsletter_task_pk],
            eta=task.send_date,
        )
        task.celery_task_id = result.id
        task.status = 'scheduled'
        task.save(update_fields=['celery_task_id', 'status'])

    def revoke(self, newsletter_task_pk):
        from celery import current_app
        try:
            task = NewsLetterTask.objects.get(pk=newsletter_task_pk)
        except NewsLetterTask.DoesNotExist:
            return

        if task.celery_task_id:
            current_app.control.revoke(task.celery_task_id, terminate=True)

        if task.status in ('pending', 'scheduled'):
            task.status = 'revoked'
            task.save(update_fields=['status'])
