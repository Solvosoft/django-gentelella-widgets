import sys
import uuid
from functools import lru_cache

from django import template
from django.contrib.staticfiles import finders
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
    return static('vendors/datatables/en-GB.json')


@lru_cache(maxsize=None)
def _moment_locale_url(lang):
    """Static URL of moment's locale file for `lang`, '' when there is none.

    moment is bundled as its core build, which speaks English and nothing else;
    the language of the page is linked as a separate 4 KB file instead of the
    375 KB build that carried all 137 of them. Loading that file also switches
    moment's global locale, which is what `fromNow()` and the date pickers read.

    Returns '' for English, and for any language whose file was not downloaded
    -- `loaddevstatic` only fetches the ones `settings.LANGUAGES` asks for --
    so a missing translation degrades to English instead of a 404.
    """
    for code in (lang.lower(), lang.lower().split('-')[0]):
        if code in ('en', 'en-us'):
            return ''
        path = 'vendors/moment/locale/%s.js' % code
        if finders.find(path):
            return static(path)
    return ''


@register.simple_tag
def get_moment_locale():
    return _moment_locale_url(get_language() or '')


@register.simple_tag(takes_context=True)
def define_true(context, val):
    setattr(context['request'], val, True)
    return ''


@register.simple_tag(takes_context=True)
def get_define(context, val):
    value = False
    if val in settings.DEFAULT_JS_IMPORTS:
        value = settings.DEFAULT_JS_IMPORTS[val]
    value = getattr(context['request'], val, value)
    return value


@register.simple_tag(takes_context=True)
def get_websocket_url(context, name, *args, default='sign_document', **kwargs):
    return settings.FIRMADOR_WS + name
