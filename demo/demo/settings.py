"""
Django settings for demo project.

Generated by 'django-admin startproject' using Django 3.0.2.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.0/ref/settings/
"""

import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '@438vu@4s#@juwf6b*s@u&%9hv&_pgk_g1%s$pp2)(+x7br-ta'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'djgentelella',
    'rest_framework',
    'demoapp',
    'djgentelella.blog',
    'djgentelella.permission_management',
    'markitup',
    "corsheaders",
    "channels",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'demo.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'demo/templates/')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'demo.wsgi.application'

# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME':
            'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

CORS_ALLOW_ALL_ORIGINS = True

# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = 'es'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.0/howto/static-files/

STATIC_URL = os.getenv('STATIC_URL', '/static/')
STATIC_ROOT = os.path.join(BASE_DIR, 'static/')
MEDIA_URL = os.getenv('MEDIA_URL', '/media/')
MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')
TINYMCE_UPLOAD_PATH = os.path.join(MEDIA_ROOT, 'tinymce')
SUMMERNOTE_UPLOAD_PATH = os.path.join(MEDIA_ROOT, 'summernote')

EMAIL_HOST = 'localhost'
EMAIL_PORT = '1025'

MARKITUP_FILTER = ('markdown.markdown', {'safe_mode': True})
MARKITUP_SET = 'markitup/sets/markdown/'
JQUERY_URL = None
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

DEFAULT_JS_IMPORTS = {
    'use_readonlywidgets': True,
    'use_flags': True
}

# FIRMADOR DIGITAL
DJANGO_ASETTINGS_MODULE = "demo.asettings"
GUNICORN_BIND = "localhost:9022" if DEBUG else "unix:/run/supervisor/gunicorn_asgi.sock"
GUNICORN_ASGI_APP = "demo.asgi:application"
GUNICORN_WSGI_APP = "demo.wsgi:application"
GUNICORN_WORKERS = 1 if DEBUG else 2
GUNICORN_WORKER_CLASS = "demo.asgi_worker.UvicornWorker"
GUNICORN_USER = "demo"
GUNICORN_GROUP = "demo"

FIRMADOR_WS = os.getenv("FIRMADOR_WS", "ws://127.0.0.1:9022/async/")
FIRMADOR_DOMAIN = os.getenv("FIRMADOR_DOMAIN", "http://localhost:9001")
FIRMADOR_VALIDA_URL = FIRMADOR_DOMAIN + "/valida/"
FIRMADOR_SIGN_URL = FIRMADOR_DOMAIN + "/firma/firme"
FIRMADOR_SIGN_COMPLETE = FIRMADOR_DOMAIN + "/firma/completa"
FIRMADOR_DELETE_FILE_URL = FIRMADOR_DOMAIN + "/firma/delete"
