import sys
import uuid

from django import template
from django.templatetags.static import static
from django.utils.safestring import mark_safe
from django.utils.translation import get_language

from djgentelella import settings
from djgentelella.utils import get_settings as get_settings_utils

register = template.Library()


@register.simple_tag(takes_context=True)
def get_settings(context, name, default='', **kwargs):
    settings = get_settings_utils(name)
    if settings:
        return mark_safe(settings)
    return default


@register.simple_tag
def get_random_uuid():
    return str(uuid.uuid4())


@register.simple_tag
def get_version():
    return sys.modules['djgentelella'].__version__


@register.simple_tag(takes_context=True)
def get_datatables_translation(context):
    lang = get_language()
    if lang and hasattr(settings, 'DATATABLES_SUPPORT_LANGUAGES'):
        if lang in settings.DATATABLES_SUPPORT_LANGUAGES:
            return settings.DATATABLES_SUPPORT_LANGUAGES[lang]
    return static("vendors/datatables/en-GB.json")


@register.simple_tag(takes_context=True)
def define_true(context, val):
    setattr(context['request'], val, True)
    return ""


@register.simple_tag(takes_context=True)
def get_define(context, val):
    value = False
    if val in settings.DEFAULT_JS_IMPORTS:
        value = settings.DEFAULT_JS_IMPORTS[val]
    value = getattr(context['request'], val, value)
    return value
