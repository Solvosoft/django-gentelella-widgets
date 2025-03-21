import os

from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "demo.settings")

bind = getattr(settings, "GUNICORN_BIND", "unix:/run/supervisor/gunicorn_wsgi.sock")
wsgi_app = getattr(settings, "GUNICORN_WSGI_APP", "demo.wsgi:application")
workers = getattr(settings, "GUNICORN_WORKERS", 1)
worker_class = getattr(settings, "GUNICORN_WORKER_CLASS",
                       "demo.asgi_worker.UvicornWorker")
user = getattr(settings, "GUNICORN_USER", "demo")
group = getattr(settings, "GUNICORN_GROUP", "demo")
