from django.apps import AppConfig


class DataSourcesConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'djgentelella.datasources'
    label = 'gtdatasources'
    verbose_name = 'Data sources'

    def ready(self):
        # Deferred on purpose: a gtdatasources.py names its models, and ready()
        # is the first moment the app registry can hand them over.
        from djgentelella.datasources.base import autodiscover  # noqa: PLC0415
        autodiscover()
