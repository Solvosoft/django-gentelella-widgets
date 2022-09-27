from django  import forms
from rest_framework.reverse import reverse_lazy

from . import models
from djgentelella.forms.forms import CustomForm
from djgentelella.widgets import core as genwidgets
from markitup.widgets import MarkItUpWidget


class EntryForm(CustomForm, forms.ModelForm):
    class Meta:
        model = models.Entry
        exclude = ('published_content', 'author')
        widgets = {
          'title':   genwidgets.TextInput,
          'content': MarkItUpWidget,
          'resume': MarkItUpWidget,
          'is_published': genwidgets.YesNoInput,
          'categories': genwidgets.SelectMultipleAdd(attrs={
              'add_url': reverse_lazy('blog:category_add')
          })
        }

class CategoryForm(CustomForm, forms.ModelForm):
    class Meta:
        model = models.Category
        fields = '__all__'
        widgets ={
            'name':genwidgets.TextInput
        }

