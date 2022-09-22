import uuid

from django.template.loader import render_to_string
from django.urls import reverse
from django.core.mail import send_mail as django_send_email
from djgentelella.models import Notification
from djgentelella import settings
from django.utils.translation import gettext_lazy as _
from django.conf import  settings as djsettings
message_type_default = list(dict(Notification.MESSAGE_TYPE).keys())


def get_site_url(request, name, **kwargs):
    rev_kwargs = kwargs['kwargs'] if 'kwargs' else {}
    rev_args = kwargs['args'] if 'args' else []

    return request.build_absolute_uri(reverse(name, args=rev_args, kwargs=rev_kwargs))


def create_notification(description, user, message_type, category=None, link=None,
                        link_prop=None, request=None, send_email=False,
                        email_subject=None, email_template=None, email_context={}):
    """
    Create a notification for provided user, and send email notification if it's set

    There is two default setting you can configurate on django settings

    - NOTIFICATION_DEFAULT_SUBJECT
    - NOTIFICATION_DEFAULT_TEMPLATE

    All settings has a default value provided by django-gentelella-widgets but you can overwrite it

    :param description: description to show
    :param user: user to be notified
    :param message_type: type of message available options (info, default, success, warning, danger) there is no priority here yet
    :param category: used for group notifications (not required)
    :param link: complete url or reverse name (see django reverse)
    :param link_prop: when is set, the link is take as reverse name, you need to provide dict of args and kwargs
    :param request: it's django request used on email and for make a complete uri on reverse
    :param send_email: True/False specify you want to send a email notification
    :param email_subject: alternative subject message
    :param email_template: alternative email template
    :param email_context: extra context for email template
    :return: notification object
    """


    if message_type not in message_type_default:
        raise ValueError("Message type are not valid (options: %s)"%("".join(message_type_default)))
    if category is None:
        category = uuid.uuid4()
    if link_prop is not None:
        if request is None:
            raise ValueError('Request is required when link_prop is set')
        if 'kwargs' not in link_prop or 'args' not in link_prop:
            raise ValueError('args and kwargs are required for reverse function')
        link = get_site_url(request, link, **link_prop)

    dev = Notification.objects.create(
        state='visible',
        user=user,
        message_type=message_type,
        description=description,
        link=link,
        category=category
    )

    if send_email:
        if email_subject is None:
            email_subject = settings.NOTIFICATION_DEFAULT_SUBJECT
        if email_template is None:
            email_template = settings.NOTIFICATION_DEFAULT_TEMPLATE
        email_context['object'] = dev
        if user.email:
            django_send_email(email_subject,
              _('This is a html email, please use a visor with HTML support'),
              djsettings.DEFAULT_FROM_EMAIL,
              [user.email],
              fail_silently=False,
              html_message=render_to_string(
                  email_template, context=email_context, request=request)
                              )

    return dev

