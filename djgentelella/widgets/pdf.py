from pathlib import Path

from django.urls import reverse_lazy

from djgentelella.widgets.core import update_kwargs
from djgentelella.widgets.files import FileChunkedUpload


class PDFViewerWidget(FileChunkedUpload):
    """
    PDF Viewer Widget with preview and chunked upload.

    Extends FileChunkedUpload to add:
    - PDF-only file filtering (accept attribute)
    - PDF preview using PDF.js (page navigation, zoom)
    - PDF-specific upload endpoint with server-side validation

    Usage:
        from djgentelella.widgets.pdf import PDFViewerWidget

        class DocumentForm(GTForm, forms.ModelForm):
            class Meta:
                model = Document
                widgets = {
                    'pdf_file': PDFViewerWidget
                }
    """
    template_name = 'gentelella/widgets/pdfviewer.html'

    def __init__(self, attrs=None, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, self.__class__.__name__,
                                  base_class='djgentelella-pdfviewer form-control')
        if attrs is None:
            attrs = {}
        attrs['accept'] = 'application/pdf,.pdf'
        if 'data-href' not in attrs:
            attrs['data-href'] = reverse_lazy('upload_pdf_view')
        if 'data-done' not in attrs:
            attrs['data-done'] = reverse_lazy('upload_pdf_done')
        super().__init__(attrs, extraskwargs=False)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['has_value'] = bool(value)
        if value:
            try:
                context['pdf_url'] = value.url
                context['pdf_name'] = Path(value.name).name
            except Exception:
                context['pdf_url'] = None
                context['pdf_name'] = None
        else:
            context['pdf_url'] = None
            context['pdf_name'] = None
        return context
