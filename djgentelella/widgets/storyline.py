import json

from .core import TextInput, update_kwargs


class UrlStoryLineInput(TextInput):
    template_name = 'gentelella/widgets/storyline.html'

    def __init__(self, csv=None, options=None, attrs=None):
        self.csv = csv
        self.options = options
        attrs = update_kwargs(attrs, self.__class__.__name__,"")
        super(UrlStoryLineInput, self).__init__(attrs=attrs, extraskwargs=False)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs=attrs)
        context['options'] = self.options
        context['csv'] = json.dumps(self.csv)
        return context
