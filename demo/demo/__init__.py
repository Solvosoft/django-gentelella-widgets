try:
    # Optional dependency ([celery] extra, not in requirements.txt): import
    # failing here would break every manage.py command, not just the worker.
    from .celery import app as celery_app
    __all__ = ('celery_app',)
except ImportError:
    pass
