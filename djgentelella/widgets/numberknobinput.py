import copy
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
    # min_value y max_value
    def __init__(self, attrs=None):
        if attrs is not None:
            attrs = attrs.copy()
        attrs["class"]="knob"
        attrs["data-displayprevious"] = "true"

        super().__init__(attrs)
