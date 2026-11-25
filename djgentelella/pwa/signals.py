from django.contrib.auth.signals import user_logged_out
from django.db.models.signals import post_save

from djgentelella.models import Notification
from djgentelella.pwa.push import on_notification_saved, on_user_logged_out


def connect():
    """A new ``Notification`` also goes out as push (``AppConfig.ready``)."""
    post_save.connect(on_notification_saved, sender=Notification,
                      dispatch_uid='djgentelella.pwa.push_notification')
    # GT_PUSH_UNSUBSCRIBE_ON_LOGOUT, checked when it is sent.
    user_logged_out.connect(on_user_logged_out,
                            dispatch_uid='djgentelella.pwa.unsubscribe_on_logout')
