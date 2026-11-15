"""The demo on PostgreSQL, for the tests tagged ``postgresql`` (the full-text
search of djgentelella.datasources). The connection comes from the libpq
environment variables::

    PGHOST=localhost PGPORT=5432 PGUSER=postgres PGPASSWORD=... PGDATABASE=demo \\
    DJANGO_SETTINGS_MODULE=demo.settings_postgres \\
    python manage.py test djgentelella.tests.Datasources_Test

``PGTESTDATABASE`` names the test database (``test_<PGDATABASE>`` by default).
"""
from .settings import *  # noqa: F401,F403
from .settings import INSTALLED_APPS, os

INSTALLED_APPS = INSTALLED_APPS + ['django.contrib.postgres']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('PGDATABASE', 'djgentelella'),
        'USER': os.getenv('PGUSER', 'postgres'),
        'PASSWORD': os.getenv('PGPASSWORD', ''),
        'HOST': os.getenv('PGHOST', 'localhost'),
        'PORT': os.getenv('PGPORT', '5432'),
        'TEST': {'NAME': os.getenv('PGTESTDATABASE') or None},
    }
}
