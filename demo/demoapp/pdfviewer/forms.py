from django import forms

from demoapp.models import PDFDocument
from djgentelella.forms.forms import GTForm
from djgentelella.widgets.core import TextInput
from djgentelella.widgets.pdf import PDFViewerWidget


class PDFDocumentForm(GTForm, forms.ModelForm):
    class Meta:
        model = PDFDocument
        fields = ['name', 'pdf_file']
        widgets = {
            'name': TextInput,
            'pdf_file': PDFViewerWidget,
        }
