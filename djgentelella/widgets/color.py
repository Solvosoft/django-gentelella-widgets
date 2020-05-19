from .core import Input, update_kwargs


class DefaultColorInput(Input):
    template_name = 'gentelella/widgets/default-color.html'

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
    template_name = 'gentelella/widgets/style-color.html'

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


"""

    agregar classes utilizando js

    attrs: 
        modificar los attr apartir de la herencia

    implementar la totalidad de widgets

    hacer un modelo para almacenar la informacion del campo

"""