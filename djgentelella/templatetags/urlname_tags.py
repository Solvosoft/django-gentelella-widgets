from django import template
from django.urls import reverse, resolve
from django.utils.http import urlencode
from djgentelella.models import PermissionsCategoryManagement
register = template.Library()


@register.simple_tag
def get_page_name(val):
    url = reverse('permissionsmanagement-list')
    parameters = {
        'urlname': val,
        'option': 1
    }
    p = urlencode(parameters)
    return url+'?'+p

@register.simple_tag
def validate_context(val):
    perms=PermissionsCategoryManagement.objects.filter(url_name__in=val.split(','))
    return perms

@register.simple_tag(takes_context=True)
def define_urlname_action(context, val):
    if not hasattr(context['request'], 'urlnamecontext'):
        setattr(context['request'],  'urlnamecontext', [])
    context['request'].urlnamecontext.append(val)
    return ""


@register.simple_tag(takes_context=True)
def get_urlname_action(context):
    value = getattr(context['request'], 'urlnamecontext', [])
    result = ''
    if value:
        result = ",".join(value)

    return result