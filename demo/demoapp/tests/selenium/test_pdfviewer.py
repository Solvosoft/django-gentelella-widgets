"""Browser test for ``PDFViewerWidget``.

The widget hands a URL to pdf.js and draws the result on a canvas, so nothing
short of a real browser can tell whether it works: the markup is identical
whether the document rendered or the promise rejected. This asserts pixels.
"""

from django.core.files.base import ContentFile
from django.test import tag

from demoapp.models import PDFDocument
from djgentelella.management.commands.loaddevstatic import PDFJS_VERSION
from .base import By, SeleniumTestCase

# One page, 200x100pt, valid enough for pdf.js to lay out and paint.
ONE_PAGE_PDF = (
    b'%PDF-1.4\n'
    b'1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n'
    b'2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n'
    b'3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 100]>>endobj\n'
    b'trailer<</Root 1 0 R>>\n'
)

# Counts the documents the page asks pdf.js for: installed before any script
# runs, it wraps the module namespace pdf.js publishes as window.pdfjsLib.
COUNT_LOADS = """
window.gtPdfLoads = 0;
let wrapped;
Object.defineProperty(window, 'pdfjsLib', {
  configurable: true,
  get() { return wrapped; },
  set(lib) {
    wrapped = Object.create(lib, {getDocument: {value: function () {
      window.gtPdfLoads++;
      return lib.getDocument.apply(lib, arguments);
    }}});
  },
});
"""


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
        # The version loaddevstatic downloads, wherever its pin is.
        self.assertEqual(self.js('return pdfjsLib.version'), PDFJS_VERSION)
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

        # The canvas is sized before pdf.js paints it, and painting finishes
        # in a later task: polled until every pixel is opaque.
        self.wait_js(
            "const c = document.querySelector('.pdfviewer-widget canvas');"
            "const px = c.getContext('2d').getImageData(0, 0, c.width, c.height)"
            ".data;"
            "let n = 0;"
            "for (let i = 3; i < px.length; i += 4) if (px[i] !== 0) n++;"
            "return n === arguments[0];",
            200 * 100, message='the page was not painted')

    def test_the_document_is_loaded_once(self):
        """The widget finds its document twice as it starts (its value and
        data-pdf-url); two loads painted the same canvas at once, and the
        second one cleared it."""
        script = self.driver.execute_cdp_cmd(
            'Page.addScriptToEvaluateOnNewDocument', {'source': COUNT_LOADS})
        self.addCleanup(self.driver.execute_cdp_cmd,
                        'Page.removeScriptToEvaluateOnNewDocument', script)
        self.open_document()
        self.wait_js(
            "const c = document.querySelector('.pdfviewer-widget canvas');"
            "return c.width === 200;", message='nothing rendered')
        self.assertEqual(self.js('return window.gtPdfLoads'), 1)

    def test_the_same_url_loads_again_once_the_load_settles(self):
        """A load in progress is shared; a finished one is not, so a file
        replaced under the same URL is fetched again."""
        script = self.driver.execute_cdp_cmd(
            'Page.addScriptToEvaluateOnNewDocument', {'source': COUNT_LOADS})
        self.addCleanup(self.driver.execute_cdp_cmd,
                        'Page.removeScriptToEvaluateOnNewDocument', script)
        self.open_document()
        self.wait_js(
            "const c = document.querySelector('.pdfviewer-widget canvas');"
            "return c.width === 200;", message='nothing rendered')
        self.assertEqual(self.js('return window.gtPdfLoads'), 1)
        self.driver.set_script_timeout(10)
        outcome = self.driver.execute_async_script(
            "const done = arguments[arguments.length - 1];"
            "const widget = $('.pdfviewer-widget');"
            "const viewer = widget.data('pdfviewer');"
            "const url = widget.data('pdf-url');"
            "const first = viewer.loadPDF(url);"
            "const shared = viewer.loadPDF(url) === first;"
            "first.then(() => viewer.loadPDF(url))"
            ".then(() => done({shared: shared, loads: window.gtPdfLoads}),"
            " (error) => done({error: String(error)}));")
        self.assertEqual(outcome, {'shared': True, 'loads': 3})

    def test_no_console_errors(self):
        self.open_document()
        severe = [entry['message'] for entry in self.driver.get_log('browser')
                  if entry['level'] == 'SEVERE']
        self.assertEqual(severe, [])

    def test_the_list_shows_the_document(self):
        self.go('/pdfviewer/')
        self.assertIn(
            'Demo', self.driver.find_element(By.TAG_NAME, 'body').text)


@tag('selenium')
class PDFViewerFileNameTest(SeleniumTestCase):
    """The stored name reaches the page as JSON the widget parses; it is text."""

    MARKUP_NAME = '<img src=x onerror=window.gtxss=1>.pdf'

    def test_a_stored_name_with_markup_is_shown_as_text(self):
        document = PDFDocument.objects.create(name='Marcado')
        PDFDocument.objects.filter(pk=document.pk).update(pdf_file=self.MARKUP_NAME)

        self.go('/pdfviewer/%d/' % document.pk)
        self.wait_js(
            "return document.querySelector('.pdf_file_messages') !== null"
            " && document.querySelector('.pdf_file_messages')"
            ".textContent.trim() !== '';",
            message='the widget never showed the file name')

        self.assertEqual(self.js(
            "return document.querySelector('.pdf_file_messages')"
            ".textContent.trim();"), self.MARKUP_NAME)
        self.assertFalse(self.js(
            "return document.querySelector('.pdf_file_messages img') !== null"
            " || window.gtxss === 1;"), 'the file name was injected as HTML')
