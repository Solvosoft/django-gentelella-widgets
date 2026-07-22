"""
Base backend class for notification dispatch.
"""


class NotificationBackend:
    """Abstract base class for notification backends.

    Subclasses must implement send(), schedule(), and revoke().
    """

    def send(self, notification_pk):
        """Send a single email notification.

        Args:
            notification_pk: Primary key of the EmailNotification.
        """
        raise NotImplementedError

    def schedule(self, newsletter_task_pk):
        """Schedule a newsletter task for future delivery.

        Args:
            newsletter_task_pk: Primary key of the NewsLetterTask.
        """
        raise NotImplementedError

    def revoke(self, newsletter_task_pk):
        """Revoke a scheduled newsletter task.

        Args:
            newsletter_task_pk: Primary key of the NewsLetterTask.
        """
        raise NotImplementedError

    def send_bulk(self, notification_pks):
        """Send multiple notifications. Default calls send() for each.

        Args:
            notification_pks: Iterable of EmailNotification primary keys.
        """
        for pk in notification_pks:
            self.send(pk)

    def retry(self, notification_pk, countdown=0):
        """Re-attempt a failed send after a backoff delay.

        Default no-op: deployments without a scheduler rely on the
        ``process_notifications`` command to pick pending notifications up
        again. Schedulers (e.g. Celery) override this to re-enqueue with a
        countdown.

        Args:
            notification_pk: Primary key of the EmailNotification.
            countdown: Delay in seconds before the retry.
        """
        return None
