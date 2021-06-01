from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.contrib.contenttypes.models import ContentType

NOTIFICATION_DEFAULT_SUBJECT = getattr(settings, 'NOTIFICATION_DEFAULT_SUBJECT',
                                     _('You have a new notification'))
NOTIFICATION_DEFAULT_TEMPLATE = getattr(settings, 'NOTIFICATION_DEFAULT_TEMPLATE',
                                     'gentelella/email/notification.html')

DEFAULT_JS_IMPORTS = getattr(settings, 'DEFAULT_JS_IMPORTS', {})

GROUP_MODEL_BASE = getattr(
    settings, 'GT_GROUP_MODEL', 'auth.Group')

USER_MODEL_BASE = getattr(
    settings, 'GT_USER_MODEL', 'auth.User')


aux_group = ContentType.objects.get(app_label=GROUP_MODEL_BASE.split('.')[0], model=GROUP_MODEL_BASE.split('.')[1].lower())
Group = aux_group.model_class()

aux_user = ContentType.objects.get(app_label=USER_MODEL_BASE.split('.')[0], model=USER_MODEL_BASE.split('.')[1].lower())
User = aux_user.model_class()