"""The demo settings on a throwaway SQLite file, closer to production."""
import os

from demo.settings import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ['MEMPROFILE_DB'],
        'OPTIONS': {'timeout': 20},
    }
}
# DEBUG=True keeps every SQL query in connection.queries: a fake leak.
DEBUG = False
ALLOWED_HOSTS = ['testserver', 'localhost']
DO_STATIC = False
# createdemo copies files into MEDIA_ROOT: keep them out of demo/media.
MEDIA_ROOT = os.path.join(os.path.dirname(os.environ['MEMPROFILE_DB']), 'media')
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
LOGGING = {'version': 1, 'disable_existing_loggers': False,
           'handlers': {'null': {'class': 'logging.NullHandler'}},
           'root': {'handlers': ['null']},
           'loggers': {'django.request': {'handlers': ['null'],
                                          'propagate': False}}}
