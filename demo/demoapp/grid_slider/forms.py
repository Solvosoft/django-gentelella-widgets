from django import forms
from demoapp import models
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as widget

attrs = {'min': '0',
         'max': '1000',
         'step': 2,
         'grid': 'true',
         'from_fixed': 'false',
         'prefix': "$",
         'to_fixed': 'false',
         'to_max': 750,
         'from_min': 200,
         'hide_min_max': 'true',
         'data-target-from': 'minimum',
         'data-target-to': 'maximum',
         }


class gridSliderForm(forms.ModelForm, GTForm):

    slider = forms.CharField(widget=widget.GridSlider(attrs))

    class Meta:
        model = models.gridSlider
        fields = '__all__'
        widgets = {
            'prevent_dragging': widget.GridSlider(attrs),
            'pre_defined_steps':widget.GridSlider(attrs),
            'default_min_and_max':widget.GridSlider(attrs),
            'minimum_and_maximum_values':widget.GridSlider(attrs),
            'hours':widget.DateGridSlider({}),
        }
