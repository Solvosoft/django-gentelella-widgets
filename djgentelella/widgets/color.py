from .core import Input


class ColorInput(Input):

    class Meta:
        js = (
            'js/bootstrap-colorpicker.min.js'
        )

    template_name = 'gentelella/widgets/colors.html'
