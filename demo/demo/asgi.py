"""
ASGI config for demo project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/howto/deployment/asgi/
"""

from djgentelella.firmador_digital.config.asgi_config import AsgiConfig

application = AsgiConfig("demo.settings").application
