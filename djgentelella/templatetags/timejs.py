from django import template



from djgentelella.widgets.core import DateFormatConverter

register = template.Library()

class DateConverter(DateFormatConverter):
    format_key = 'DATE_INPUT_FORMATS'

class DateTimeConverter(DateFormatConverter):
    format_key = 'DATETIME_INPUT_FORMATS'

@register.simple_tag
def get_date_format():
    return DateConverter().get_format_js()

@register.simple_tag
def get_datetime_format():
    return DateTimeConverter().get_format_js()