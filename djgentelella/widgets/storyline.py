from django.core.exceptions import ImproperlyConfigured

from .core import TextInput, update_kwargs


class UrlStoryLineInput(TextInput):
    template_name = 'gentelella/widgets/storyline.html'

    def __init__(self, attrs=None):
        if attrs is None or "data-url" not in attrs:
            raise ImproperlyConfigured("You must add data-url on attrs")
        attrs = update_kwargs(attrs, self.__class__.__name__, "")
        super(UrlStoryLineInput, self).__init__(attrs=attrs, extraskwargs=False)

    def render(self, name, value, attrs=None, renderer=None):
        self.value = value

        return super().render(name, value, attrs=attrs, renderer=renderer)

    def build_attrs(self, base_attrs, extra_attrs=None):
        """Build an attribute dictionary."""
        if extra_attrs is not None:
            if 'required' in extra_attrs:
                extra_attrs.pop('required')
            if 'disabled' in extra_attrs:
                extra_attrs.pop('disabled')

        attrs = super().build_attrs(base_attrs, extra_attrs=extra_attrs)
        if self.value is not None:
            attrs['data-url'] = self.value

        return attrs
