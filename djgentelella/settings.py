from django.conf import settings
from django.utils.translation import gettext_lazy as _
import time
import os.path
from datetime import timedelta
from django.utils.module_loading import import_string
from django.core.serializers.json import DjangoJSONEncoder

NOTIFICATION_DEFAULT_SUBJECT = getattr(settings, 'NOTIFICATION_DEFAULT_SUBJECT',
                                     _('You have a new notification'))
NOTIFICATION_DEFAULT_TEMPLATE = getattr(settings, 'NOTIFICATION_DEFAULT_TEMPLATE',
                                     'gentelella/email/notification.html')

DEFAULT_JS_IMPORTS = getattr(settings, 'DEFAULT_JS_IMPORTS', {})

DEFAULT_GROUP_MODEL_BASE = 'GT_GROUP_MODEL'

DEFAULT_USER_MODEL_BASE = 'GT_USER_MODEL'

DEFAULT_GROUP_MODEL = 'auth.Group'

DEFAULT_USER_MODEL = 'auth.User'

GROUP_MODEL_BASE = getattr(
    settings, DEFAULT_GROUP_MODEL_BASE, DEFAULT_GROUP_MODEL)

USER_MODEL_BASE = getattr(
    settings, DEFAULT_USER_MODEL_BASE, DEFAULT_USER_MODEL)

try:
    from django.contrib.contenttypes.models import ContentType
    aux_group = ContentType.objects.get(app_label=GROUP_MODEL_BASE.split('.')[0], model=GROUP_MODEL_BASE.split('.')[1].lower())
    Group = aux_group.model_class()

    aux_user = ContentType.objects.get(app_label=USER_MODEL_BASE.split('.')[0], model=USER_MODEL_BASE.split('.')[1].lower())
    User = aux_user.model_class()
except Exception as e:
    from django.contrib.auth.models import User, Group

#####################################################
##    Chuncked Upload
############################################

# How long after creation the upload will expire
DEFAULT_EXPIRATION_DELTA = timedelta(days=1)
EXPIRATION_DELTA = getattr(settings, 'CHUNKED_UPLOAD_EXPIRATION_DELTA',
                           DEFAULT_EXPIRATION_DELTA)

# Path where uploading files will be stored until completion
DEFAULT_UPLOAD_PATH = 'chunked_uploads/%Y/%m/%d'
UPLOAD_PATH = getattr(settings, 'CHUNKED_UPLOAD_PATH', DEFAULT_UPLOAD_PATH)


# upload_to function to be used in the FileField
def default_upload_to(instance, filename):
    filename = os.path.join(UPLOAD_PATH, instance.upload_id + '.part')
    return time.strftime(filename)


UPLOAD_TO = getattr(settings, 'CHUNKED_UPLOAD_TO', default_upload_to)

try:
    STORAGE = getattr(settings, 'CHUNKED_UPLOAD_STORAGE_CLASS', lambda: None)()
except TypeError:
    STORAGE = import_string(getattr(settings, 'CHUNKED_UPLOAD_STORAGE_CLASS', lambda: None))()

# Function used to encode response data. Receives a dict and return a string
DEFAULT_ENCODER = DjangoJSONEncoder().encode
ENCODER = getattr(settings, 'CHUNKED_UPLOAD_ENCODER', DEFAULT_ENCODER)

# Content-Type for the response data
DEFAULT_CONTENT_TYPE = 'application/json'
CONTENT_TYPE = getattr(settings, 'CHUNKED_UPLOAD_CONTENT_TYPE',
                       DEFAULT_CONTENT_TYPE)

# Max amount of data (in bytes) that can be uploaded. `None` means no limit
DEFAULT_MAX_BYTES = None
MAX_BYTES = getattr(settings, 'CHUNKED_UPLOAD_MAX_BYTES', DEFAULT_MAX_BYTES)

#############################################################
####   END UPLOAD CHUNKED