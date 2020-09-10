from django import forms
from demoapp import models
from djgentelella.forms.forms import CustomForm
from djgentelella.widgets import core as widget


class gridSliderForm(forms.ModelForm, CustomForm):
    slider = forms.CharField(widget=widget.GridSlider(attrs={'min': '0',
                                                       'max': '1000',
                                                       'step': 2,
                                                       'final': 50,
                                                       'from': 20,
                                                       'to': 100,
                                                       'data-from':'minimum',
                                                       'data-to':'maximum',
                                                       }))

    class Meta:
        model = models.gridSlider
        fields = '__all__'
        widgets = {
            'maximum': widget.NumberInput,
            'minimum': widget.NumberInput,
        }
