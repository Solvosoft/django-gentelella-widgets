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
