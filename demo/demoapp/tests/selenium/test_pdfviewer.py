"""Browser test for ``PDFViewerWidget``.

The widget hands a URL to pdf.js and draws the result on a canvas, so nothing
short of a real browser can tell whether it works: the markup is identical
whether the document rendered or the promise rejected. This asserts pixels.
"""

from django.core.files.base import ContentFile
from django.test import tag

from demoapp.models import PDFDocument
from .base import By, SeleniumTestCase

# One page, 200x100pt, valid enough for pdf.js to lay out and paint.
ONE_PAGE_PDF = (
    b'%PDF-1.4\n'
    b'1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n'
    b'2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n'
    b'3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 100]>>endobj\n'
    b'trailer<</Root 1 0 R>>\n'
)


@tag('selenium')
class PDFViewerWidgetTest(SeleniumTestCase):
    def setup_data(self):
        self.document = PDFDocument.objects.create(name='Demo')
        self.document.pdf_file.save(
            'demo.pdf', ContentFile(ONE_PAGE_PDF), save=True)

    def open_document(self):
        self.go('/pdfviewer/%d/' % self.document.pk)
        self.wait_js(
            "return document.querySelectorAll('.pdfviewer-widget canvas')"
            ".length > 0",
            message='the widget never drew a canvas')

    def test_pdfjs_is_loaded_with_a_worker(self):
        """A missing workerSrc makes pdf.js parse on the UI thread instead."""
        self.open_document()
        self.assertEqual(self.js('return pdfjsLib.version'), '6.2.108')
        self.assertTrue(
            self.js('return pdfjsLib.GlobalWorkerOptions.workerSrc'),
            'pdf.js fell back to its fake worker')

    def test_the_document_is_actually_painted(self):
        """The canvas is sized from the PDF and every pixel is opaque.

        pdf.js 6 dropped getDocument's bare-string shorthand, and the failure
        mode is silent: the canvas stays at its default 300x150 and fully
        transparent while the DOM looks exactly the same.
        """
        self.open_document()
        self.wait_js(
            "const c = document.querySelector('.pdfviewer-widget canvas');"
            "return c && c.width > 0 && c.width !== 300;",
            message='the canvas kept its default size -- nothing rendered')

        size = self.js(
            "const c = document.querySelector('.pdfviewer-widget canvas');"
            "return [c.width, c.height];")
        self.assertEqual(size, [200, 100], 'canvas not sized from the MediaBox')

        opaque = self.js(
            "const c = document.querySelector('.pdfviewer-widget canvas');"
            "const px = c.getContext('2d').getImageData(0, 0, c.width, c.height)"
            ".data;"
            "let n = 0;"
            "for (let i = 3; i < px.length; i += 4) if (px[i] !== 0) n++;"
            "return n;")
        self.assertEqual(opaque, 200 * 100, 'the page was not painted')

    def test_no_console_errors(self):
        self.open_document()
        severe = [entry['message'] for entry in self.driver.get_log('browser')
                  if entry['level'] == 'SEVERE']
        self.assertEqual(severe, [])

    def test_the_list_shows_the_document(self):
        self.go('/pdfviewer/')
        self.assertIn(
            'Demo', self.driver.find_element(By.TAG_NAME, 'body').text)
