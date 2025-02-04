from django.urls import path
from djgentelella.firmador_digital.consumers.sign import SignConsumer

websocket_urlpatterns = [path("async/sign_document", SignConsumer.as_asgi())]
