from django import forms

from demoapp.models import ChunkedUploadItem
from djgentelella.widgets.core import TextInput
from djgentelella.widgets.files import FileChunkedUpload
from djgentelella.forms.forms import GTForm

class ChunkedUploadItemForm(GTForm, forms.ModelForm):
    fileexample = forms.FileField(widget=FileChunkedUpload, required=False)
    class Meta:
        model = ChunkedUploadItem
        fields = '__all__'
        widgets = {
            'name': TextInput,
            'fileexample': FileChunkedUpload

        }