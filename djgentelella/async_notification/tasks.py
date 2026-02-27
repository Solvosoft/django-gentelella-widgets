"""
Celery tasks for async notification dispatch.

These tasks are only loaded if Celery is available.
"""

try:
    from celery import shared_task

    @shared_task(bind=True, max_retries=3)
    def send_email_task(self, notification_pk):
        """Celery task to send a single email notification."""
        from djgentelella.async_notification.sending import do_send_notification
        do_send_notification(notification_pk)

    @shared_task(bind=True, max_retries=3)
    def send_newsletter_task(self, newsletter_task_pk):
        """Celery task to send a newsletter."""
        from djgentelella.async_notification.sending import do_send_newsletter
        do_send_newsletter(newsletter_task_pk)

except ImportError:
    pass
