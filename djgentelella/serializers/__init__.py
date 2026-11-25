from django.utils import formats
from rest_framework import serializers
from rest_framework.fields import DateField, DateTimeField

from djgentelella.markdown import render_markdown


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


class DateFieldWithEmptyString(DateField):
    def to_internal_value(self, value):
        if not value:
            return None
        return super(DateFieldWithEmptyString, self).to_internal_value(value)


class DateTimeFieldFieldWithEmptyString(DateTimeField):
    def to_internal_value(self, value):
        if not value:
            return None
        return super(DateTimeFieldFieldWithEmptyString, self).to_internal_value(value)


class DataTableSerializer(serializers.Serializer):
    """The envelope DataTables expects from a server-side source.

    Subclass it and declare ``data`` with the row serializer::

        class BookDataTableSerializer(DataTableSerializer):
            data = serializers.ListField(child=BookSerializer(), required=True)

    Left undeclared, ``data`` passes the rows through as they are.
    """
    data = serializers.ListField(required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)


class GTMarkdownHTMLField(serializers.ReadOnlyField):
    """The Markdown text of ``source`` as cleaned HTML
    (:func:`djgentelella.markdown.render_markdown`), read only: what a
    ``<name>_html`` column shows with the ``markdownprint`` renderer of
    ``datatables.js`` or ``<% it.<name>_html | safe %>`` in an ObjectCRUD
    detail template. The text of the user is never sent as HTML."""

    def to_representation(self, value):
        if value in (None, ''):
            return ''
        return str(render_markdown(value))
