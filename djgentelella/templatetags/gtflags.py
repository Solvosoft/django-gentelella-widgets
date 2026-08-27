"""Template tags for country flags.

Replace the ``flag-icons`` CSS classes, which are gone along with the 6.35 MB
stylesheet that carried them::

    {% load gtflags %}
    {% flag 'cr' %}                      instead of  <i class="fi fi-cr"></i>
    {% flag 'cr' square=True %}          instead of  <i class="fi fi-cr fis"></i>
"""
from django import template
from django.urls import reverse
from django.utils.html import format_html

from djgentelella.flags import flag_url, get_flag_codes

register = template.Library()


@register.simple_tag
def flag(code, css_class='', title='', square=False):
    """A flag as an inline ``<svg>`` pointing into the sprite.

    One request serves every flag on the page, and the browser caches it across
    pages. Unknown codes render nothing rather than a broken reference.
    """
    if code not in get_flag_codes():
        return ''
    classes = 'gt-flag gt-flag-square' if square else 'gt-flag'
    if css_class:
        classes = '%s %s' % (classes, css_class)
    return format_html(
        '<svg class="{}" role="img" aria-label="{}">'
        '<use href="{}#fi-{}"></use></svg>',
        classes, title or code.upper(), flag_sprite_url(), code)


@register.simple_tag
def flag_sprite_url():
    """URL of the whole sprite, for hand-written ``<use>`` references."""
    return reverse('flag_sprite')


@register.simple_tag(name='flag_url')
def flag_url_tag(code, **params):
    """URL of one flag, for ``<img src>``.

    Takes the same ``size``, ``shape`` and ``title`` parameters the view does.
    """
    return flag_url(code, **params)
