"""
ASGI config for demo project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/howto/deployment/asgi/
"""

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'demo.settings')

# application = get_asgi_application()

#  Para usar digital_signature
from djgentelella.firmador_digital.config.asgi_config import AsgiConfig
application = AsgiConfig("demo.settings").application
