"""
Backend abstraction layer for notification dispatch.

Provides lazy-loading singleton for the configured backend with
autodetection support (Celery if available, otherwise sync).
"""

from django.utils.module_loading import import_string

from djgentelella.async_notification.settings import ASYNC_NOTIFICATION_BACKEND

_backend_instance = None


def _get_default_backend_path():
    """Determine the default backend based on environment.

    Returns CeleryBackend path if Celery is installed and
    CELERY_BROKER_URL is configured, otherwise SyncBackend.
    """
    try:
        import celery  # noqa: F401
        from django.conf import settings
        if getattr(settings, 'CELERY_BROKER_URL', None):
            return 'djgentelella.async_notification.backends.celery.CeleryBackend'
    except ImportError:
        pass

    try:
        from django.tasks import task  # noqa: F401
        from django.conf import settings
        if getattr(settings, 'TASKS', None):
            return 'djgentelella.async_notification.backends.django_tasks.DjangoTasksBackend'
    except ImportError:
        pass

    return 'djgentelella.async_notification.backends.sync.SyncBackend'


def get_backend():
    """Get the notification backend instance (lazy singleton).

    Returns:
        NotificationBackend instance.
    """
    global _backend_instance
    if _backend_instance is None:
        backend_path = ASYNC_NOTIFICATION_BACKEND
        if backend_path is None:
            backend_path = _get_default_backend_path()
        backend_class = import_string(backend_path)
        _backend_instance = backend_class()
    return _backend_instance


def reset_backend():
    """Reset the cached backend instance. Useful for testing."""
    global _backend_instance
    _backend_instance = None
