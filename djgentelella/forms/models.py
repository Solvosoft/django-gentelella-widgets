from django import forms

from djgentelella.models import Help
from djgentelella.widgets import core as genwidgets
from .forms import CustomForm


class HelpForm(CustomForm, forms.ModelForm):
    class Meta:
        model = Help
        fields = ['help_title', 'help_text']
        widgets = {
            'help_title': genwidgets.TextInput,
            'help_text': genwidgets.Textarea
        }
