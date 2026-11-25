"""Settings of :mod:`djgentelella.wizard`, read when they are used (so
``override_settings`` works) and importable before the app registry is ready.

``GT_WIZARD_DRAFT_EXPIRATION``
    How long a draft lives after its last change: a ``timedelta`` or a number
    of days. Default: 30 days. An expired draft is not offered nor resumed;
    ``manage.py delete_expired_wizard_drafts`` deletes them.
``GT_WIZARD_DRAFT_STORAGE``
    Where :class:`~djgentelella.wizard.views.GTWizardView` keeps drafts when
    the view does not say: ``'session'`` (default) or ``'model'``
    (:class:`~djgentelella.models.WizardDraft`).
"""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

DEFAULT_EXPIRATION = timedelta(days=30)
STORAGES = ('session', 'model')


def draft_expiration():
    value = getattr(settings, 'GT_WIZARD_DRAFT_EXPIRATION', DEFAULT_EXPIRATION)
    if isinstance(value, timedelta):
        return value
    return timedelta(days=float(value))


def expired_before(now=None):
    """The moment before which a draft (by its last change) is expired."""
    return (now or timezone.now()) - draft_expiration()


def default_storage():
    value = getattr(settings, 'GT_WIZARD_DRAFT_STORAGE', 'session')
    return value if value in STORAGES else 'session'
