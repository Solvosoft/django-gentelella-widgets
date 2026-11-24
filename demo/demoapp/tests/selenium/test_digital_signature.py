"""Browser test for the preview of ``DigitalSignatureInput``.

The widget renders a signed reference to its file and pdf.js asks the preview
endpoint for it: the page only shows the document if the reference the
server rendered is accepted, and only to a user allowed to see it (W15).
The signing itself needs Firmador Libre and the websocket, not run here.
"""

from django.core.files.base import ContentFile
from django.test import tag

from demoapp.models import DigitalSignature
from djgentelella.firmador_digital.access import load_document_reference
from .base import SeleniumTestCase
from .test_pdfviewer import ONE_PAGE_PDF

INPUT = '.widget-digital-signature input[data-renderurl]'

# The status the preview endpoint gives the page for the widget's reference.
FETCH_STATUS = """
const input = document.querySelector(arguments[0]);
window.gtPreviewStatus = null;
fetch(input.dataset.renderurl + '?' + input.dataset.renderattr,
      {credentials: 'same-origin'})
  .then(r => { window.gtPreviewStatus = r.status; });
"""


@tag('selenium')
class DigitalSignaturePreviewTest(SeleniumTestCase):
    def setup_data(self):
        self.document = DigitalSignature.objects.create(filename='demo.pdf')
        self.document.file.save('demo.pdf', ContentFile(ONE_PAGE_PDF), save=True)
        self.addCleanup(self.document.file.delete, save=False)

    def open_document(self):
        self.go('/digitalsignature/%d/' % self.document.pk)
        self.wait_js('return !!document.querySelector(arguments[0])', INPUT,
                     message='the signature widget was not rendered')

    def preview_status(self):
        self.js(FETCH_STATUS, INPUT)
        return self.wait_js('return window.gtPreviewStatus',
                            message='the preview endpoint never answered')

    def test_the_widget_renders_a_signed_reference(self):
        self.open_document()
        value = self.js('return document.querySelector(arguments[0])'
                        '.dataset.value', INPUT)
        self.assertEqual(load_document_reference(value)['pk'], self.document.pk)

    def test_the_document_is_shown_to_who_may_see_it(self):
        self.open_document()
        self.wait_js(
            "const n = document.querySelector("
            "'.widget-digital-signature .page_count');"
            "return n && n.textContent.trim() === '1';",
            message='pdf.js never loaded the document of the reference')
        self.assertEqual(self.preview_status(), 200)

    def test_not_to_a_user_without_permission(self):
        self.open_document()
        self.user.is_superuser = False
        self.user.save()
        self.assertEqual(self.preview_status(), 404)
