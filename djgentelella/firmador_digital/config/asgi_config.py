import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application


class AsgiConfig:

    def __init__(self, settings_module: str):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
        self.application = self._build_application()

    def _build_application(self):
        # get_asgi_application() dispara django.setup(); recién después
        # se pueden importar consumers/models.
        http_application = get_asgi_application()

        from djgentelella.firmador_digital.config.websocket_urls import (
            websocket_urlpatterns,
        )

        return ProtocolTypeRouter({
            "http": http_application,
            "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
        })

    def __call__(self, scope, receive, send):
        return self.application(scope, receive, send)
