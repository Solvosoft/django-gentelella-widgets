from django import template
from djgentelella.models import PermissionsCategoryManagement
from django.urls import resolve

register = template.Library()

@register.simple_tag
def get_page_name(request):
    url = resolve(request.path_info).url_name
    return url

@register.simple_tag(takes_context=True)
def define_true(context, val):
    setattr(context['request'], val, True)
    return ""

@register.simple_tag(takes_context=True)
def get_define(context, val):
    value = getattr(context['request'], val, True)
    return ""