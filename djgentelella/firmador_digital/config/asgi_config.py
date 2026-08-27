import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application


class AsgiConfig:

    def __init__(self, settings_module: str):
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)
        self.application = self._build_application()

    def _build_application(self):
        # get_asgi_application() dispara django.setup(); recién después
        # se pueden importar consumers/models.
        http_application = get_asgi_application()

        # App registry: the consumers reached through websocket_urls import
        # models, so this cannot move to the top of the module -- it is only
        # importable once get_asgi_application() above has run django.setup().
        from djgentelella.firmador_digital.config.websocket_urls import (  # noqa: PLC0415, E501
            websocket_urlpatterns,
        )

        return ProtocolTypeRouter({
            'http': http_application,
            'websocket': AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
        })

    def __call__(self, scope, receive, send):
        return self.application(scope, receive, send)
