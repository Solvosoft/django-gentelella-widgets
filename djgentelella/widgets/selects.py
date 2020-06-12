from djgentelella.widgets.core import Select, update_kwargs


class AutocompleteSelect(Select):
    template_name = 'gentelella/widgets/autocomplete.html'
    option_template_name = 'gentelella/widgets/select_option.html'

    def __init__(self, attrs=None, choices=(), extraskwargs=True, multiple=None):
        if extraskwargs:
            attrs = update_kwargs(attrs, self.__class__.__name__,
                                  base_class='form-control ')
        if 'url' not in attrs:
            raise ValueError('Autocomplete requires url in attrs')
        else:
            self.url = attrs['url']

        self.multiple = ''
        if multiple:
            self.multiple = 'multiple="multiple"'
        super().__init__(attrs,  choices=choices, extraskwargs=False)

    def get_context(self, name, value, attrs):
        context = super().get_context(name,value,attrs)
        context['url'] = self.url
        context['multiple'] = self.multiple
        return context
