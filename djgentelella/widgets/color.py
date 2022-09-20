from .core import TextInput, update_kwargs


class DefaultColorInput(TextInput):
    template_name = 'gentelella/widgets/color_default.html'

    class Media:
        css = {
            "all": (
                'vendors/bootstrap-colorpicker/bootstrap-colorpicker.min.css',
            )
        }
        js = (
            'vendors/bootstrap-colorpicker/bootstrap-colorpicker.min.js',
        )

    def __init__(self, attrs=None):
        attrs = update_kwargs(attrs, self.__class__.__name__,
                              base_class='form-control input-group color-input-field')
        super(DefaultColorInput, self).__init__(attrs=attrs, extraskwargs=False)


class StyleColorInput(DefaultColorInput):
    template_name = 'gentelella/widgets/color_style.html'

    def __init__(self, attrs=None):
        super(DefaultColorInput, self).__init__(attrs)


class HorizontalBarColorInput(DefaultColorInput):

    def __init__(self, attrs=None):
        attrs = update_kwargs(attrs, self.__class__.__name__,
                              base_class='form-control input-group color-input-field-horizontal')
        super(DefaultColorInput, self).__init__(attrs=attrs, extraskwargs=False)


class VerticalBarColorInput(DefaultColorInput):

    def __init__(self, attrs=None):
        attrs = update_kwargs(attrs, self.__class__.__name__,
                              base_class='form-control input-group color-input-field-vertical-rgb')
        super(DefaultColorInput, self).__init__(attrs=attrs, extraskwargs=False)


class InlinePickerColor(DefaultColorInput):
    template_name = 'gentelella/widgets/color_inline.html'

    def __init__(self, attrs=None):
        attrs = update_kwargs(attrs, self.__class__.__name__,
                              base_class='hide form-control input-group color-input-field-inline-picker')
        super(DefaultColorInput, self).__init__(attrs=attrs, extraskwargs=False)
