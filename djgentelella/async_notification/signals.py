"""
Signal handlers for async_notification.

Dispatches immediate email sending when an EmailNotification is created
with enqueued=False.
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from djgentelella.async_notification.models import EmailNotification


@receiver(post_save, sender=EmailNotification)
def on_notification_created(sender, instance, created, **kwargs):
    """Send notification immediately when created with enqueued=False.

    Only fires when:
    - The instance was just created (created=True)
    - enqueued is False (immediate send requested)
    - Status is 'pending'

    The dispatch is deferred to ``transaction.on_commit`` so a rollback of the
    creating transaction never leaves a delivered email with no persisted
    notification; outside an atomic block Django runs it immediately, keeping
    the synchronous behavior. Re-entrancy is not a concern: the backend's own
    status updates re-fire this handler with ``created=False``, which returns
    early.
    """
    if not created:
        return
    if instance.enqueued:
        return
    if instance.status != 'pending':
        return

    pk = instance.pk

    def _dispatch():
        from djgentelella.async_notification.backends import get_backend
        get_backend().send(pk)

    transaction.on_commit(_dispatch)
