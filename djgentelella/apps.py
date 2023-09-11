from django.apps import AppConfig
import logging  # Importa el módulo de registro

class DjgentelellaConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'djgentelella'

    def ready(self):
        super(DjgentelellaConfig, self).ready()

        # Configura el registro
        logger = logging.getLogger(__name__)

        # Agrega un mensaje de registro para verificar que el método ready se está ejecutando
        logger.info("La aplicación DjgentelellaConfig está lista.")

        # Importa y ejecuta tu comando personalizado aquí
        from django.core import management
        management.call_command('show_permissions')
