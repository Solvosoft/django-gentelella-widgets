from django import forms
from demoapp import models
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as widget


class gridSliderForm(forms.ModelForm, GTForm):

    grid_slider = forms.CharField(widget=widget.GridSlider(attrs={'data-min': '0',
                                                                  'data-max': '1000',
                                                                  'data-step': 2,
                                                                  'data-grid': 'true',
                                                                  'data-from_fixed': 'false',
                                                                  'data-prefix': "$",
                                                                  'data-to_fixed': 'false',
                                                                  'data-to_max': 800,
                                                                  'data-from_min': 200,
                                                                  'data-hide_min_max': 'true',
                                                                  'data-target-from': 'minimum',
                                                                  'data-target-to': 'maximum',
                                                                  }
                                                           ))

    grid_timer = forms.CharField(widget=widget.DateGridSlider(attrs={'data_min': '2020-09-12 00:00',
                                                                     'data_max': '2020-12-12 24:00',
                                                                     'data_from': '2020-11-12 00:00',
                                                                     'data-target': 'datetime',
                                                                     }))

    grid_ages = forms.CharField(widget=widget.SingleGridSlider(attrs={'data-min': '0',
                                                                      'data-max': '100',
                                                                      'data_from': '20',
                                                                      'data-prefix': ' ',
                                                                      'data-target': 'age',
                                                                      }))

    class Meta:
        model = models.gridSlider
        fields = '__all__'
        widgets = {
            'minimum': widget.HiddenInput,
            'maximum': widget.HiddenInput,
            'datetime': widget.HiddenInput,
            'age': widget.HiddenInput
        }
