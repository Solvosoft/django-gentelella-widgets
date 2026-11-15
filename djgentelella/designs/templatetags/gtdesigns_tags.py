"""Template filters of the classic CRUD pages a design serves."""

import os.path

from django import template
from django.db import models
from django.utils.html import format_html
from django.utils.translation import gettext as _

register = template.Library()


@register.filter
def design_value(obj, name):
    """The value of ``obj.<name>`` as text: escaped, never a link the row
    could forge (``crud_tags.format_value`` writes file names unescaped)."""
    model_field = obj._meta.get_field(name)
    if model_field.many_to_many:
        return ', '.join(str(item) for item in getattr(obj, name).all())
    if model_field.choices:
        return getattr(obj, 'get_%s_display' % name)()
    value = getattr(obj, name)
    if value is None:
        return ''
    if isinstance(value, bool):
        return _('Yes') if value else _('No')
    if isinstance(value, models.fields.files.FieldFile):
        if not value:
            return ''
        return format_html('<a href="{}">{}</a>', value.url,
                           os.path.basename(value.name))
    return str(value)
