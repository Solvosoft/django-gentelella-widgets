import json

from .core import TextInput, update_kwargs


class UrlStoryLineInput(TextInput):
    template_name = 'gentelella/widgets/storyline.html'

    def __init__(self, csv=None, options=None, attrs=None):
        self.csv = csv
        self.options = options
        attrs = update_kwargs(attrs, self.__class__.__name__,"")
        super(UrlStoryLineInput, self).__init__(attrs=attrs, extraskwargs=False)

    def render(self, name, value, attrs=None, renderer=None):
        self.value = value

        return super().render(name, value, attrs=attrs, renderer=renderer)

    def build_attrs(self, base_attrs, extra_attrs=None):
        """Build an attribute dictionary."""
        attrs = super().build_attrs(base_attrs, extra_attrs=extra_attrs)
        if self.value is not None:
            attrs['data-url'] = self.value

        return attrs