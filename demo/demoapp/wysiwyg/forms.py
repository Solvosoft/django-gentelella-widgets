from django import forms
from demoapp.models import WysiwygModel
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import tinymce as widget


class EditorTinymce(forms.ModelForm, GTForm):
    class Meta():
        model = WysiwygModel
        fields = '__all__'
        widgets = {
            'information': widget.EditorTinymce,
            'extra_information': widget.EditorTinymce,
        }

