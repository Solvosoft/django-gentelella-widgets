from django import template
from django.urls import reverse
from django.utils.http import urlencode

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