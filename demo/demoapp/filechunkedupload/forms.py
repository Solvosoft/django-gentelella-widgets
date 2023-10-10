from django import forms

from demoapp.models import ChunkedUploadItem
from djgentelella.forms.forms import GTForm
from djgentelella.widgets.core import TextInput
from djgentelella.widgets.files import FileChunkedUpload


class ChunkedUploadItemForm(GTForm, forms.ModelForm):
    fileexample = forms.FileField(widget=FileChunkedUpload, required=False)

    class Meta:
        model = ChunkedUploadItem
        fields = '__all__'
        widgets = {
            'name': TextInput,
            'fileexample': FileChunkedUpload

        }
