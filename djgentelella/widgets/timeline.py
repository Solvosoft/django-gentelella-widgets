from .core import TextInput, update_kwargs


class UrlTimeLineInput(TextInput):
    template_name = 'gentelella/widgets/timeline.html'

    def __init__(self, attrs=None):
        attrs = update_kwargs(attrs, self.__class__.__name__,
                              base_class='form-control')
        super(UrlTimeLineInput, self).__init__(attrs=attrs, extraskwargs=False)

    def render(self, name, value, attrs=None, renderer=None):
        self.value = value
        return super().render(name, value, attrs=attrs, renderer=renderer )

    def build_attrs(self, base_attrs, extra_attrs=None):
        """Build an attribute dictionary."""
        attrs = super().build_attrs(base_attrs, extra_attrs=extra_attrs)
        if self.value is not None:
            attrs['data-url'] = self.value
        return attrs