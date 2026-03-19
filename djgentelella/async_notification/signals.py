"""
Signal handlers for async_notification.

Dispatches immediate email sending when an EmailNotification is created
with enqueued=False.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from djgentelella.async_notification.models import EmailNotification

# Anti-recursion guard: tracks PKs currently being sent
_sending_in_progress = set()


@receiver(post_save, sender=EmailNotification)
def on_notification_created(sender, instance, created, **kwargs):
    """Send notification immediately when created with enqueued=False.

    Only fires when:
    - The instance was just created (created=True)
    - enqueued is False (immediate send requested)
    - The instance is not already being processed
    - Status is 'pending'
    """
    if not created:
        return
    if instance.enqueued:
        return
    if instance.pk in _sending_in_progress:
        return
    if instance.status != 'pending':
        return

    _sending_in_progress.add(instance.pk)
    try:
        from djgentelella.async_notification.backends import get_backend
        get_backend().send(instance.pk)
    finally:
        _sending_in_progress.discard(instance.pk)
