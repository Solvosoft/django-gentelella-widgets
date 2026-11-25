"""The Celery task of ``GT_PUSH_QUEUE`` (``'celery'``/``'auto'``): a new
notification sent as push by a worker. Defined only with Celery installed."""

try:
    from celery import shared_task

    @shared_task(ignore_result=True)
    def push_notification_task(notification_pk):
        # Deferred: a worker imports this module before the app registry is
        # ready, and the push module imports the models.
        from djgentelella.models import Notification  # noqa: PLC0415
        from djgentelella.pwa.push import push_notification  # noqa: PLC0415
        notification = Notification.objects.filter(pk=notification_pk).first()
        if notification is None:
            return 0
        return push_notification(notification)

except ImportError:
    pass
