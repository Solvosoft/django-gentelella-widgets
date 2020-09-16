from django import forms
from demoapp import models
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as widget

attrs = {'data-min': '0',
         'data-max': '1000',
         'data-step': 2,
         'data-grid': 'true',
         'data-from_fixed': 'false',
         'data-prefix': "$",
         'data-to_fixed': 'false',
         'data-to_max': 750,
         'data-from_min': 200,
         'data-hide_min_max': 'true',
         'data-target-from': 'minimum',
         'data-target-to': 'maximum',
         }


class gridSliderForm(forms.ModelForm, GTForm):

    slider = forms.CharField(widget=widget.GridSlider(attrs))
    timer = forms.CharField(widget=widget.DateGridSlider({'data_min': '2020-09-12',
                                                          'data_max': '2020-12-12',
                                                          'data_from': '2020-11-12',
                                                          }))

    class Meta:
        model = models.gridSlider
        fields = '__all__'
        widgets = {
            'minimum': widget.HiddenInput,
            'maximum': widget.HiddenInput
        }
