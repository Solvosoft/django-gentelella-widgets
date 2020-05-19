from .core import Input, update_kwargs


class DefaultColorInput(Input):
    template_name = 'gentelella/widgets/color_default.html'

    class Media:
        css = {
            "all": (
                'vendors/mjolnic-bootstrap-colorpicker/bootstrap-colorpicker.min.css',
            )
        }
        js = (
            'vendors/mjolnic-bootstrap-colorpicker/bootstrap-colorpicker.min.js',
            'gentelella/js/color.js',
        )

    def __init__(self, attrs=None):
        attrs = update_kwargs(attrs, self.__class__.__name__,
                              base_class='form-control input-group color-input-field')
        super(DefaultColorInput, self).__init__(attrs=attrs, extraskwargs=False)


class StyleColorInput(DefaultColorInput):
    template_name = 'gentelella/widgets/color_style.html'

    def __init__(self, attrs=None):
        super(DefaultColorInput, self).__init__()


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
                              base_class='form-control input-group color-input-field-inline-picker')
        super(DefaultColorInput, self).__init__(attrs=attrs, extraskwargs=False)
