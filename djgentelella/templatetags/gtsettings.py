from django import template
from django.utils.safestring import mark_safe
from djgentelella.utils import get_settings as get_settings_utils
import uuid

register = template.Library()

@register.simple_tag(takes_context=True)
def get_settings(context,  name, **kwargs):
    settings=get_settings_utils(name)
    if settings:
        return mark_safe(settings)
    return ""

@register.simple_tag
def get_random_uuid():
    return str(uuid.uuid4())