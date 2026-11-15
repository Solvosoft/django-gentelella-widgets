from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DesignsConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'djgentelella.designs'
    label = 'gtdesigns'
    verbose_name = _('Designs')

    def ready(self):
        # The gtdesigns.py modules expose models as well as registering
        # components, and both must be in place wherever Django runs: a
        # management command never imports the URLconf.
        from djgentelella.designs import registry  # noqa: PLC0415 (app registry)

        registry.get_components()
