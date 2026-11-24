"""Smallest project that runs djgentelella, plus optional apps from the env.

``MEMPROFILE_APPS``  comma separated extra apps (``djgentelella.flows``...).
``MEMPROFILE_NO_GT=1`` drops djgentelella and DRF: the Django-only floor.
"""
import os

SECRET_KEY = 'memprofile-not-secret'
DEBUG = False
ALLOWED_HOSTS = ['testserver', 'localhost']
NO_GT = os.environ.get('MEMPROFILE_NO_GT') == '1'
EXTRA_APPS = [a for a in os.environ.get('MEMPROFILE_APPS', '').split(',') if a]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]
if not NO_GT:
    # sites is required by djgentelella (check djgentelella.E001).
    INSTALLED_APPS += ['django.contrib.sites', 'djgentelella', 'rest_framework']
    INSTALLED_APPS += EXTRA_APPS
else:
    INSTALLED_APPS += ['django.contrib.sites']

SITE_ID = 1
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]
ROOT_URLCONF = 'memprofile.urls_minimal'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
USE_TZ = True
STATIC_URL = '/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = '/tmp/memprofile-media'
JQUERY_URL = None
