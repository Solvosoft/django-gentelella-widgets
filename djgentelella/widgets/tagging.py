import json

from django.forms import Widget

from djgentelella.widgets.core import Input


class TaggingInput(Input):
    input_type = 'text'
    template_name = 'gentelella/widgets/tagging.html'

    def __init__(self, attrs=None, extraskwargs=True):
        attrs = attrs or {}
        attrs['data-widget'] = self.__class__.__name__
        super().__init__(attrs, extraskwargs=False)

    def value_from_datadict(self, data, files, name):
        value = data.get(name)
        if value:
            data = json.loads(value)
            value = ", ".join([item['value'] for item in data])
        return value


class EmailTaggingInput(Input):
    input_type = 'text'
    template_name = 'gentelella/widgets/tagging.html'

    def __init__(self, attrs=None, extraskwargs=True):
        attrs = attrs or {}
        attrs['data-widget'] = self.__class__.__name__
        super().__init__(attrs, extraskwargs=False)

    def value_from_datadict(self, data, files, name):
        value = data.get(name)
        if value:
            data = json.loads(value)
            value = ", ".join([item['value'] for item in data])
        return value


class RemoteAutocompleteEmailTagifyWidget(Widget):
    template_name = "gentelella/widgets/tagifyselect.html"

    def build_attrs(self, base_attrs, extra_attrs=None):
        """Build an attribute dictionary."""
        dev = {**base_attrs, **(extra_attrs or {})}
        dev["data-url"] = self.base_url
        dev["data-widget"] = self.__class__.__name__
        return dev

    @classmethod
    def newwidget(cls, url):
        widget = type("RemoteAutocompleteEmailTagifyWidget", cls.__bases__,
                      dict(cls.__dict__))
        widget.base_url = url
        return widget
