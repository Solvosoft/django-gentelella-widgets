from django import forms
from demoapp.models import Img
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as widget


class ImageForm(forms.ModelForm, GTForm):
    class Meta:
        model = Img
        fields = '__all__'
        widgets = {
            'imges_x': widget.SelectMultipleImages,
        }
