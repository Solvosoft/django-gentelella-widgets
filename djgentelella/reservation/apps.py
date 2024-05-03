from django.apps import AppConfig


class DjreservationConfig(AppConfig):
    name = 'djgentelella.reservation'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        import djgentelella.reservation.signals
        AppConfig.ready(self)
