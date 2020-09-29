from django import forms
from demoapp.models import WysiwygModel 
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import wysiwyg as widget

class WysiwygForm(forms.ModelForm,GTForm):

  class Meta():
    model=WysiwygModel
    fields='__all__'
    widgets={
      'information': widget.TextareaWysiwyg,
    }

    