from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.db.utils import  OperationalError

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
except OperationalError as e:
    from django.contrib.auth.models import User, Group