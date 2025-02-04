
import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from djgentelella.firmador_digital.config.websocket_urls import websocket_urlpatterns

class AsgiConfig:

    def __init__(self, settings_module: str):
        # Configuramos la variable de entorno con el módulo de settings
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
        # variable de la aplicación
        self.application = self._build_application()

    def _build_application(self):
        """
        Construye y retorna la aplicación ASGI compuesta.
        """
        return ProtocolTypeRouter({
            "http": get_asgi_application(),
            "websocket": AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            ),
        })

    def __call__(self, scope, receive, send):
        """
        Permite que la instancia sea llamada como una aplicación ASGI.
        """
        return self.application(scope, receive, send)
