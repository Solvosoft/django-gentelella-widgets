from django import forms

from demoapp.models import TaggingModel
from djgentelella.forms.forms import GTForm
from djgentelella.widgets.tagging import TaggingInput, EmailTaggingInput


class TaggingForm(GTForm, forms.ModelForm):
    class Meta:
        model = TaggingModel
        fields = '__all__'
        widgets = {

        'text_list': TaggingInput,
        'email_list':  EmailTaggingInput,
        'area_list': TaggingInput
        }