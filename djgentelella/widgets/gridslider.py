from django.forms.widgets import Input
from djgentelella.widgets.core import update_kwargs

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
      
class SingleGridSlider(Input):
    input_type = 'text'
    template_name = 'gentelella/widgets/input.html'
    def __init__(self, attrs={}, extraskwargs=True):
        attrs = update_kwargs(attrs, self.__class__.__name__)
        super().__init__(attrs)

