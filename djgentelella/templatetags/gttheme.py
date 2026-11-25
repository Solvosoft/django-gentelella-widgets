"""``{% gt_theme_css %}`` and ``{% gt_theme_logo_url %}``: the theme of the
request's Site (:mod:`djgentelella.theme`)."""

from django import template
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html

from djgentelella.sites import get_current_site
from djgentelella.theme.resolve import resolve_theme

register = template.Library()


def _theme(context):
    request = context.get('request')
    return resolve_theme(get_current_site(request))


@register.simple_tag(takes_context=True)
def gt_theme_css(context):
    """The ``<link>`` of the theme's stylesheet, at a URL with its version;
    nothing without a theme, or on the roller page (``gt_theme_preview``),
    which links the values being edited instead."""
    if context.get('gt_theme_preview'):
        return ''
    found = _theme(context)
    if found is None:
        return ''
    pk, version, _logo = found
    try:
        url = reverse('gt_theme_css', args=[pk])
    except NoReverseMatch:  # the project did not include djgentelella's URLs
        return ''
    return format_html('<link href="{}?v={}" rel="stylesheet" data-gt-theme="{}">',
                       url, version, pk)


@register.simple_tag(takes_context=True)
def gt_theme_logo_url(context):
    """The URL of the logo of the theme, or ``''``."""
    found = _theme(context)
    if found is None or not found[2]:
        return ''
    try:
        return '%s?v=%s' % (reverse('gt_theme_logo', args=[found[0]]), found[1])
    except NoReverseMatch:
        return ''
