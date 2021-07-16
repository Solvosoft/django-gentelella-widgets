from .core import TextInput, update_kwargs


class UrlTimeLineInput(TextInput):
    template_name = 'gentelella/widgets/timeline.html'


    def __init__(self, attrs=None):
        attrs = update_kwargs(attrs, self.__class__.__name__,
                              base_class='form-control input-group color-input-field')
        super(UrlTimeLineInput, self).__init__(attrs=attrs, extraskwargs=False)
