import os

from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                      os.getenv("DJANGO_ASETTINGS_MODULE", "demo.asettings"))

bind = getattr(settings, "UVICORN_BIND", "127.0.0.1:9022")
wsgi_app = getattr(settings, "GUNICORN_ASGI_APP", "demo.asgi:application")
workers = getattr(settings, "UVICORN_WORKER", 1)
worker_class = getattr(settings, "UVICORN_WORKER_CLASS",
                       "demo.asgi_worker.UvicornWorker")
