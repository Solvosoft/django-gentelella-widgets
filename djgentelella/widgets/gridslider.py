from django.forms.widgets import Input
from djgentelella.widgets.core import update_kwargs
import json
import datetime

class HiddenInput(Input):
    input_type = 'hidden'
    template_name = 'gentelella/widgets/text.html'

class GridSlider(Input):
    input_type = 'text'
    template_name = 'gentelella/widgets/input.html'

    def __init__(self, attrs=None, extraskwargs=True):
        attrs = update_kwargs(attrs, self.__class__.__name__)
        super().__init__(attrs)

class DateGridSlider(Input):
    input_type = 'text'
    template_name = 'gentelella/widgets/input.html'

    def __init__(self, attrs=None, extraskwargs=True):
        attrs = update_kwargs(attrs, self.__class__.__name__)
        super().__init__(attrs)

    def value_from_datadict(self, data, files, name):
        value = data.get(name)
        s = int(value) / 1000.0
        value= datetime.datetime.fromtimestamp(s).strftime('%Y-%m-%d %H:%M:%S')
        return value

    
class SingleGridSlider(Input):
    input_type = 'text'
    template_name = 'gentelella/widgets/input.html'
    def __init__(self, attrs={}, extraskwargs=True):
        attrs = update_kwargs(attrs, self.__class__.__name__)
        super().__init__(attrs)

