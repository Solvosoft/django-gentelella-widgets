from django import forms
from demoapp import models
from djgentelella.forms.forms import CustomForm
from djgentelella.widgets import core as widget


class gridSliderForm(forms.ModelForm, CustomForm):
    slider = forms.CharField(widget=widget.GridSlider(attrs={'min': '0',
                                                             'max': '1000',
                                                             'step': 2,
                                                             'grid': 'true',
                                                             'from_fixed': 'false',
                                                             'prefix': "$",
                                                             'to_fixed': 'false',
                                                             'to_max': 750,
                                                             'from_min':200,
                                                             'hide_min_max': 'true',
                                                             'data-target-from': 'minimum',
                                                             'data-target-to': 'maximum',
                                                             }))

    class Meta:
        model = models.gridSlider
        fields = '__all__'
        widgets = {
            'maximum': widget.NumberInput,
            'minimum': widget.NumberInput,
        }
