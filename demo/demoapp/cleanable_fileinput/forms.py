
from django import forms
from django.utils.translation import gettext_lazy as _
from djgentelella.forms.forms import GTForm
from djgentelella.widgets.cleanable_fileinput import CleanableFileInput
from demoapp.models import ChunkedUploadItem
from djgentelella.widgets import core as gtwidgets

class CleanableFileInputForm(GTForm, forms.ModelForm):

    class Meta:
        model = ChunkedUploadItem
        fields = '__all__'
        widgets = {
            'name': gtwidgets.TextInput,
            'fileexample': CleanableFileInput
        }
