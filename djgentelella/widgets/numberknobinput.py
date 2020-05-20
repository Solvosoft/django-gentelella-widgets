from django.forms.widgets import Input
from django.forms import widgets
from .core import update_kwargs

class NumberKnobInput(Input):
    input_type = 'number'
    template_name = 'gentelella/widgets/number_knob_input.html'
    class Media:
        js = (
            'gentelella/vendors/jquery-knob/jquery.knob.min.js',
            'gentelella/js/knob_input.js'
        )

    def __init__(self, attrs=None):
        self.attrs = {} if attrs is None else attrs.copy()
        self.attrs["class"]="knob"
        self.attrs["data-displayprevious"] = "true"

        super().__init__(self.attrs)
