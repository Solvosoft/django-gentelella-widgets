from django.forms.widgets import Input


class NumberKnobInput(Input):
    input_type = 'number'
    template_name = 'gentelella/widgets/number_knob_input.html'

    def __init__(self, attrs=None):
        self.attrs = {} if attrs is None else attrs.copy()
        self.attrs["data-widget"]=self.__class__.__name__
        self.attrs["data-displayprevious"] = "true"

        super().__init__(self.attrs)
