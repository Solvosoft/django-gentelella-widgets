from django.utils import formats
from rest_framework.fields import DateField, DateTimeField


class GTDateField(DateField):

    def __init__(self, allow_empty_str=True, format=None, input_formats=None, **kwargs):
        self.allow_empty_str = allow_empty_str
        self.format = format or formats.get_format('DATE_INPUT_FORMATS')[0]
        self.input_formats = input_formats or [
            formats.get_format('DATE_INPUT_FORMATS')[0]]

        super().__init__(format=self.format, input_formats=self.input_formats, **kwargs)

    def to_internal_value(self, value):
        if not value and self.allow_empty_str:
            return None
        return super().to_internal_value(value)


class GTDateTimeField(DateTimeField):
    def __init__(self, allow_empty_str=True, format=None, input_formats=None, **kwargs):
        self.allow_empty_str = allow_empty_str
        self.format = format or formats.get_format('DATETIME_INPUT_FORMATS')[0]
        self.input_formats = input_formats or [
            formats.get_format('DATETIME_INPUT_FORMATS')[0]]

        super().__init__(format=self.format, input_formats=self.input_formats, **kwargs)

    def to_internal_value(self, value):
        if not value and self.allow_empty_str:
            return None
        return super().to_internal_value(value)
