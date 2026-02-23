from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def render_data_attrs(context):
    attrs = []
    for key, value in context.flatten().items():
        if key.startswith('data_'):
            attr_name = key.replace('_', '-')
            clean_value = str(value).strip('"').strip("'")
            attrs.append(f'{attr_name}="{clean_value}"')

    return mark_safe(' '.join(attrs))
