from django.db.models.signals import post_save

from djgentelella.models import Notification
from djgentelella.pwa.push import on_notification_saved


def connect():
    """A new ``Notification`` also goes out as push (``AppConfig.ready``)."""
    post_save.connect(on_notification_saved, sender=Notification,
                      dispatch_uid='djgentelella.pwa.push_notification')
