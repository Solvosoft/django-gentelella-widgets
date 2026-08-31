from django import forms
from rest_framework.reverse import reverse_lazy

from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as genwidgets
from djgentelella.widgets.tinymce import EditorTinymce
from . import models


class EntryForm(GTForm, forms.ModelForm):
    class Meta:
        model = models.Entry
        exclude = ('published_content', 'author')
        widgets = {
            'title': genwidgets.TextInput,
            'content': EditorTinymce,
            'resume': EditorTinymce,
            'is_published': genwidgets.YesNoInput,
            'categories': genwidgets.SelectMultipleAdd(attrs={
                'add_url': reverse_lazy('blog:category_add')
            })
        }


class CategoryForm(GTForm, forms.ModelForm):
    class Meta:
        model = models.Category
        fields = '__all__'
        widgets = {
            'name': genwidgets.TextInput
        }
