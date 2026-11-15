from django.apps import AppConfig

from djgentelella import checks  # noqa: F401 -- registers the system checks


class DjgentelellaConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'djgentelella'

    def ready(self):
        # The app registry is not ready at import time, and authorization
        # imports models.
        from djgentelella.authorization import autodiscover  # noqa: PLC0415
        autodiscover()
