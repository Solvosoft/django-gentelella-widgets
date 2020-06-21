from django.conf import settings
from django.utils.translation import ugettext_lazy as _

NOTIFICATION_DEFAULT_SUBJECT = getattr(settings, 'NOTIFICATION_DEFAULT_SUBJECT',
                                     _('You have a new notification'))
NOTIFICATION_DEFAULT_TEMPLATE = getattr(settings, 'NOTIFICATION_DEFAULT_TEMPLATE',
                                     'gentelella/email/notification.html')

DEFAULT_JS_IMPORTS = getattr(settings, 'DEFAULT_JS_IMPORTS', {})