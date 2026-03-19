"""
Django 6 Tasks backend — dispatches notifications as Django background tasks.

Requires Django 6+ with TASKS configured in settings.
"""

from djgentelella.async_notification.backends.base import NotificationBackend


class DjangoTasksBackend(NotificationBackend):
    """Sends notifications via Django 6 native task queue."""

    def send(self, notification_pk):
        from djgentelella.async_notification.tasks import django_send_email_task
        django_send_email_task.enqueue(notification_pk)

    def schedule(self, newsletter_task_pk):
        from djgentelella.async_notification.tasks import django_send_newsletter_task
        from djgentelella.async_notification.models import NewsLetterTask
        try:
            task = NewsLetterTask.objects.get(pk=newsletter_task_pk)
        except NewsLetterTask.DoesNotExist:
            return

        result = django_send_newsletter_task.using(run_after=task.send_date).enqueue(newsletter_task_pk)
        task.celery_task_id = str(result.id)
        task.status = 'scheduled'
        task.save(update_fields=['celery_task_id', 'status'])

    def revoke(self, newsletter_task_pk):
        from djgentelella.async_notification.models import NewsLetterTask
        try:
            task = NewsLetterTask.objects.get(pk=newsletter_task_pk)
        except NewsLetterTask.DoesNotExist:
            return

        if task.celery_task_id:
            try:
                from django_tasks.backends.database.models import DBTaskResult
                result = DBTaskResult.objects.get(pk=task.celery_task_id)
                result.cancel()
            except Exception:
                pass

        if task.status in ('pending', 'scheduled'):
            task.status = 'revoked'
            task.save(update_fields=['status'])
