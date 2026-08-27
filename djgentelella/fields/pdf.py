from pathlib import Path

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from djgentelella.widgets.pdf import PDFViewerWidget


class PDFFileField(forms.FileField):
    """
    Django form field with PDF validation.

    Validates that uploaded files:
    - Have a .pdf extension
    - Have application/pdf content type
    - Start with PDF magic bytes (%PDF-)

    Usage:
        from djgentelella.fields.pdf import PDFFileField

        class DocumentForm(forms.Form):
            pdf_file = PDFFileField(widget=PDFViewerWidget())
    """

    PDF_MAGIC_BYTES = b'%PDF-'

    default_error_messages = {
        'invalid_extension': _('Only PDF files are allowed. '
                               'Got file with extension: %(extension)s'),
        'invalid_content_type': _('Invalid file type: %(content_type)s. '
                                  'Only PDF files are allowed.'),
        'invalid_pdf': _('File does not appear to be a valid PDF.'),
    }

    def __init__(self, *args, **kwargs):
        if 'widget' not in kwargs:
            kwargs['widget'] = PDFViewerWidget()
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        # Handle delete action (False)
        if data is False:
            return data

        file = super().clean(data, initial)

        if not file:
            return file

        # Validate extension
        filename = file.name.lower() if file.name else ''
        if not filename.endswith('.pdf'):
            extension = Path(filename).suffix if filename else 'unknown'
            raise ValidationError(
                self.error_messages['invalid_extension'],
                code='invalid_extension',
                params={'extension': extension}
            )

        # Validate content type
        content_type = getattr(file, 'content_type', None)
        if content_type and content_type != 'application/pdf':
            raise ValidationError(
                self.error_messages['invalid_content_type'],
                code='invalid_content_type',
                params={'content_type': content_type}
            )

        # Validate PDF magic bytes
        try:
            file.seek(0)
            first_bytes = file.read(len(self.PDF_MAGIC_BYTES))
            file.seek(0)
            if first_bytes != self.PDF_MAGIC_BYTES:
                raise ValidationError(
                    self.error_messages['invalid_pdf'],
                    code='invalid_pdf'
                )
        except (IOError, OSError):
            pass

        return file
