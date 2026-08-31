from django.forms.widgets import Input


class NumberKnobInput(Input):
    """A number field drawn as a circular dial.

    The dial is ``gentelella/js/base/knob.js`` plus ``css/knob.css``; the input
    itself stays in the middle of it as the value, the readout and the control
    the keyboard reaches. The bounds are therefore declared twice on purpose:
    ``data-min`` / ``data-max`` / ``data-step`` are what the dial reads, and the
    plain ``min`` / ``max`` / ``step`` mirrored from them are what makes the
    browser's own arrow keys, validation and screen-reader announcement agree
    with it.
    """

    input_type = 'number'
    template_name = 'gentelella/widgets/number_knob_input.html'

    #: data-* option -> the native attribute that has to say the same thing.
    NATIVE_BOUNDS = {'data-min': 'min', 'data-max': 'max', 'data-step': 'step'}

    def __init__(self, attrs=None):
        self.attrs = {} if attrs is None else attrs.copy()
        self.attrs['data-widget'] = self.__class__.__name__
        self.attrs['data-displayprevious'] = 'true'
        for option, native in self.NATIVE_BOUNDS.items():
            if option in self.attrs and native not in self.attrs:
                self.attrs[native] = self.attrs[option]

        super().__init__(self.attrs)
