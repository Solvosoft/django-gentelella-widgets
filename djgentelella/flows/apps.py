from importlib import import_module
from importlib.util import find_spec

from django.apps import AppConfig, apps
from django.utils.translation import gettext_lazy as _


class FlowsConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'djgentelella.flows'
    label = 'gtflows'
    verbose_name = _('Flows')

    def ready(self):
        # Flows must be registered wherever Django runs -- a Celery worker or a
        # management command never imports the URLconf, where the other gt*
        # modules are discovered. Importing an app's gtflows needs its models,
        # which is why it happens here and not at module level.
        for config in apps.get_app_configs():
            name = config.name + '.gtflows'
            if find_spec(name) is not None:
                import_module(name)
        # The engine listens to task_completed to move the flows on.
        import_module('djgentelella.flows.base')
