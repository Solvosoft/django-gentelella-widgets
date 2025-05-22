from django import forms

from demoapp.models import Img
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import selects


class ImageForm(GTForm, forms.ModelForm):
    class Meta:
        model = Img
        fields = '__all__'
        widgets = {
            'multi_image': selects.AutocompleteSelectMultipleImage("imagebasename"),
            'related_name': selects.AutocompleteSelectImage("imagebasename"),
        }
