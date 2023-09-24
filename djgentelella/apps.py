from django.apps import AppConfig

from django.db.models.signals import post_migrate

def my_callback(sender, **kwargs):


    from django.core import management
    management.call_command('show_permissions')

class DjgentelellaConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'djgentelella'

    def ready(self):
        post_migrate.connect(my_callback, sender=self)
