from django import template
from django.utils.safestring import mark_safe

from djgentelella.models import GentelellaSettings

register = template.Library()


@register.simple_tag(takes_context=True)
def get_settings(context,  name, **kwargs):
    settings = GentelellaSettings.objects.filter(
        key=name
    ).first()
    if settings:
        return mark_safe(settings.value)
    return ""