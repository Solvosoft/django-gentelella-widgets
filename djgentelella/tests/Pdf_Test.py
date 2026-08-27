"""
Unit tests for PDFViewerWidget, PDFFileField, and PDF upload views.
"""
import json
from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from djgentelella.fields.pdf import PDFFileField
from djgentelella.widgets.files import FileChunkedUpload
from djgentelella.widgets.pdf import PDFViewerWidget

User = get_user_model()


def create_pdf_content():
    """Create minimal valid PDF content with magic bytes."""
    return b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF'


class TestPDFViewerWidgetInit(TestCase):
    """Test widget initialization."""

    def test_accept_attribute(self):
        widget = PDFViewerWidget()
        self.assertIn('application/pdf', widget.attrs.get('accept', ''))
        self.assertIn('.pdf', widget.attrs.get('accept', ''))

    def test_template_name(self):
        widget = PDFViewerWidget()
        self.assertEqual(widget.template_name, 'gentelella/widgets/pdfviewer.html')

    def test_upload_urls(self):
        widget = PDFViewerWidget()
        self.assertIn('/upload/pdf/', str(widget.attrs.get('data-href')))
        self.assertIn('/upload/pdf/done/', str(widget.attrs.get('data-done')))

    def test_extends_file_chunked_upload(self):
        widget = PDFViewerWidget()
        self.assertIsInstance(widget, FileChunkedUpload)


class TestPDFViewerWidgetFormatValue(TestCase):
    """Test JSON serialization of file values."""

    def test_format_value_with_file(self):
        widget = PDFViewerWidget()
        mock_file = MagicMock()
        mock_file.name = 'uploads/2024/document.pdf'
        mock_file.url = '/media/uploads/2024/document.pdf'

        result = widget.format_value(mock_file)
        data = json.loads(result)

        self.assertEqual(data['name'], 'uploads/2024/document.pdf')
        self.assertEqual(data['display_name'], 'document.pdf')
        self.assertEqual(data['url'], '/media/uploads/2024/document.pdf')

    def test_format_value_empty(self):
        widget = PDFViewerWidget()
        self.assertEqual(widget.format_value(None), '')


class TestPDFViewerWidgetParseValue(TestCase):
    """Test JSON parsing from form data."""

    def test_parse_value_with_token(self):
        widget = PDFViewerWidget()
        value = '{"token": "abc123", "display_name": "doc.pdf"}'
        result = widget.parse_value(value)
        self.assertEqual(result['token'], 'abc123')

    def test_parse_value_with_url(self):
        widget = PDFViewerWidget()
        value = '{"name": "doc.pdf", "url": "/media/doc.pdf"}'
        result = widget.parse_value(value)
        self.assertEqual(result['url'], '/media/doc.pdf')

    def test_parse_value_with_delete_action(self):
        widget = PDFViewerWidget()
        value = '{"url": "/media/doc.pdf", "actions": "delete"}'
        result = widget.parse_value(value)
        self.assertEqual(result['actions'], 'delete')

    def test_parse_value_invalid_json(self):
        widget = PDFViewerWidget()
        self.assertIsNone(widget.parse_value('not valid json'))

    def test_parse_value_missing_keys(self):
        widget = PDFViewerWidget()
        self.assertIsNone(widget.parse_value('{"foo": "bar"}'))

    def test_parse_value_empty(self):
        widget = PDFViewerWidget()
        self.assertIsNone(widget.parse_value(''))


class TestPDFViewerWidgetValueFromDatadict(TestCase):
    """Test form submission handling."""

    def test_value_from_datadict_delete_action(self):
        widget = PDFViewerWidget()
        data = {'pdf_field': '{"url": "/media/doc.pdf", "actions": "delete"}'}
        result = widget.value_from_datadict(data, {}, 'pdf_field')
        self.assertFalse(result)

    def test_value_from_datadict_no_value(self):
        widget = PDFViewerWidget()
        data = {'pdf_field': ''}
        result = widget.value_from_datadict(data, {}, 'pdf_field')
        self.assertIsNone(result)

    def test_value_from_datadict_existing_url(self):
        widget = PDFViewerWidget()
        data = {'pdf_field': '{"url": "/media/doc.pdf", "name": "doc.pdf"}'}
        result = widget.value_from_datadict(data, {}, 'pdf_field')
        self.assertIsNone(result)


class TestPDFViewerWidgetGetContext(TestCase):
    """Test widget context for template rendering."""

    def test_get_context_has_value_false(self):
        widget = PDFViewerWidget()
        context = widget.get_context('pdf_field', None, {})
        self.assertFalse(context['has_value'])
        self.assertIsNone(context['pdf_url'])
        self.assertIsNone(context['pdf_name'])

    def test_get_context_has_value_true(self):
        widget = PDFViewerWidget()
        mock_file = MagicMock()
        mock_file.name = 'uploads/test.pdf'
        mock_file.url = '/media/uploads/test.pdf'

        context = widget.get_context('pdf_field', mock_file, {})
        self.assertTrue(context['has_value'])
        self.assertEqual(context['pdf_url'], '/media/uploads/test.pdf')
        self.assertEqual(context['pdf_name'], 'test.pdf')


class TestPDFFileField(TestCase):
    """Test form field validation."""

    def test_clean_valid_pdf(self):
        field = PDFFileField()
        pdf_content = create_pdf_content()
        file = SimpleUploadedFile('test.pdf', pdf_content,
                                  content_type='application/pdf')
        result = field.clean(file)
        self.assertEqual(result, file)

    def test_clean_invalid_extension(self):
        field = PDFFileField()
        file = SimpleUploadedFile('test.txt', b'content',
                                  content_type='text/plain')
        with self.assertRaises(ValidationError) as cm:
            field.clean(file)
        self.assertEqual(cm.exception.code, 'invalid_extension')

    def test_clean_invalid_content_type(self):
        field = PDFFileField()
        pdf_content = create_pdf_content()
        file = SimpleUploadedFile('test.pdf', pdf_content,
                                  content_type='text/plain')
        with self.assertRaises(ValidationError) as cm:
            field.clean(file)
        self.assertEqual(cm.exception.code, 'invalid_content_type')

    def test_clean_invalid_magic_bytes(self):
        field = PDFFileField()
        file = SimpleUploadedFile('test.pdf', b'not a pdf',
                                  content_type='application/pdf')
        with self.assertRaises(ValidationError) as cm:
            field.clean(file)
        self.assertEqual(cm.exception.code, 'invalid_pdf')

    def test_clean_delete_action(self):
        field = PDFFileField()
        result = field.clean(False)
        self.assertFalse(result)

    def test_clean_none_when_not_required(self):
        field = PDFFileField(required=False)
        result = field.clean(None)
        self.assertIsNone(result)


class TestPDFChunkedUploadView(TestCase):
    """Test server-side upload validation."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='password'
        )
        self.url = reverse('upload_pdf_view')

    def test_upload_unauthenticated(self):
        pdf_content = create_pdf_content()
        response = self.client.post(self.url, {
            'file': SimpleUploadedFile('test.pdf', pdf_content,
                                       content_type='application/pdf')
        })
        self.assertEqual(response.status_code, 403)

    def test_upload_valid_pdf(self):
        self.client.login(username='testuser', password='password')
        pdf_content = create_pdf_content()
        response = self.client.post(self.url, {
            'file': SimpleUploadedFile('test.pdf', pdf_content,
                                       content_type='application/pdf')
        })
        self.assertEqual(response.status_code, 200)

    def test_upload_invalid_content_type(self):
        self.client.login(username='testuser', password='password')
        response = self.client.post(self.url, {
            'file': SimpleUploadedFile('test.txt', b'content',
                                       content_type='text/plain')
        })
        self.assertEqual(response.status_code, 400)

    def test_upload_invalid_extension(self):
        self.client.login(username='testuser', password='password')
        pdf_content = create_pdf_content()
        response = self.client.post(self.url, {
            'file': SimpleUploadedFile('test.doc', pdf_content,
                                       content_type='application/pdf')
        })
        self.assertEqual(response.status_code, 400)

    def test_upload_invalid_magic_bytes(self):
        self.client.login(username='testuser', password='password')
        response = self.client.post(self.url, {
            'file': SimpleUploadedFile('test.pdf', b'not a pdf',
                                       content_type='application/pdf')
        })
        self.assertEqual(response.status_code, 400)
