from django import forms
from markitup.widgets import MarkItUpWidget
from rest_framework.reverse import reverse_lazy

from djgentelella.forms.forms import CustomForm, GTForm
from djgentelella.widgets import core as genwidgets
from widgets.files import FileChunkedUpload
from widgets.wysiwyg import TextareaWysiwyg
from . import models


class EntryForm(GTForm, forms.ModelForm):
    #feature_image = forms.FileField(widget=FileChunkedUpload, required=False)
    class Meta:
        model = models.Entry
        exclude = ('published_content', 'author')
        widgets = {
            'title': genwidgets.TextInput,
            'content': TextareaWysiwyg,
            'resume': TextareaWysiwyg,
            'is_published': genwidgets.YesNoInput,
            'categories': genwidgets.SelectMultipleAdd(attrs={
                'add_url': reverse_lazy('blog:category_add')
            }),
          #  'feature_image': FileChunkedUpload,
        }


class CategoryForm(CustomForm, forms.ModelForm):
    class Meta:
        model = models.Category
        fields = '__all__'
        widgets = {
            'name': genwidgets.TextInput
        }
