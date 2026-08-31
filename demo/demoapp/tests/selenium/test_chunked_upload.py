"""Browser tests for ``FileChunkedUpload``.

The upload is a conversation, not a request: the file is sliced in the browser,
each slice is POSTed in order with a ``Content-Range`` the server checks
against the offset it has stored, and a final call hands over an md5 the server
recomputes from what it assembled. Every part of that is javascript, and none
of it shows up in a python test -- the widget renders the same markup whether
the upload works or answers "Offsets do not match".

So these drive a real file through a real browser and then look at what
actually landed on the server.
"""

import json
from pathlib import Path

from django.core.files.base import ContentFile
from django.test import tag

from demoapp.models import ChunkedUploadItem
from djgentelella.models import ChunkedUpload
from .base import By, SeleniumTestCase

WIDGET = '#id_fileexample'
#: Bigger than the 100 kB slice the widget uses, so the upload is genuinely
#: chunked -- three requests plus the completion -- and not one POST that
#: happens to look like it works.
PAYLOAD = (b'djgentelella chunked upload test payload\n' * 6000)


@tag('selenium')
class ChunkedUploadWidgetTest(SeleniumTestCase):

    def upload(self, name='demo.txt', content=PAYLOAD):
        path = self.write_temp_file(name, content)
        self.go('/chunkedupload/')
        self.assert_widget_ready(WIDGET)
        # The input is inside the widget's own markup and is what the browser
        # hands the file to; send_keys on a file input is the upload.
        self.driver.find_element(By.CSS_SELECTOR, WIDGET).send_keys(path)
        return path

    def stored_value(self):
        """What the hidden field will submit: {token, display_name}."""
        raw = self.js(
            "return document.querySelector('input.chunkedvalue').value;")
        return json.loads(raw) if raw else None

    def test_a_file_larger_than_one_chunk_arrives_whole(self):
        self.upload()

        self.wait.until(lambda d: self.stored_value(),
                        'the widget never wrote its token into the form')
        value = self.stored_value()
        self.assertEqual(value['display_name'], 'demo.txt')

        upload = ChunkedUpload.objects.get(upload_id=value['token'])
        self.assertEqual(upload.offset, len(PAYLOAD),
                         'the assembled file is not the size that was sent')
        with upload.file.open('rb') as stored:
            self.assertEqual(stored.read(), PAYLOAD,
                             'what arrived is not what was sent')

    def test_the_completion_call_is_accepted(self):
        """The md5 has to be ready *before* the last chunk is acknowledged.

        It used to be computed alongside the upload, so a small file finished
        first and the completion request went out with an empty checksum -- the
        server answers "Both 'upload_id' and 'md5' are required".
        """
        # The driver is shared by the class and get_log drains what it
        # returns, so empty it before the upload under test.
        self.driver.get_log('browser')
        self.upload(name='small.txt', content=b'tiny')

        self.wait.until(lambda d: self.stored_value(),
                        'the widget never wrote its token into the form')
        self.wait_js(
            "return document.querySelector('[class*=_progress] i.fa-check')"
            "  !== null;",
            message='the upload never reported completion')

        severe = [entry['message'] for entry in self.driver.get_log('browser')
                  if entry['level'] == 'SEVERE']
        self.assertEqual(severe, [], 'the upload logged an error')

    def test_progress_is_reported_while_it_runs(self):
        self.upload()

        # Either a percentage on the way or the tick at the end: both come from
        # the same element, and a fast local server can beat the first read.
        self.wait_js(
            "const el = document.querySelector('[class*=_progress]');"
            "return el && (/\\d+%/.test(el.textContent)"
            "  || el.querySelector('i.fa-check') !== null);",
            message='no progress was ever shown')

    def test_a_rejected_upload_tells_the_user(self):
        """A file over the server's limit must surface, not fail silently."""
        self.go('/chunkedupload/')
        self.assert_widget_ready(WIDGET)

        # Drive the uploader directly at an endpoint that will refuse it: no
        # csrf token, so the very first slice comes back 403.
        outcome = self.driver.execute_async_script(
            "const done = arguments[arguments.length - 1];"
            "gt_chunked_upload({"
            "  file: new File(['abc'], 'x.txt'),"
            "  url: '/djgentelella/upload/',"
            "  done_url: '/djgentelella/upload/done/',"
            "  csrf: 'not-a-csrf-token'"
            "}).then(() => done('resolved'))"
            "  .catch(e => done('rejected: ' + e.message));")

        self.assertTrue(outcome.startswith('rejected: '),
                        f'a refused upload resolved instead: {outcome}')
        # Not "undefined" and not empty: the message is what reaches the person
        # who tried, through Swal.
        self.assertTrue(len(outcome) > len('rejected: '),
                        'the rejection carried no message to show')


@tag('selenium')
class ChunkedUploadFileFieldTest(SeleniumTestCase):
    """The widget on a plain model ``FileField``, which is the point of it.

    ``value_from_datadict`` turns the token the browser posts into the uploaded
    file, and ``format_value`` renders a file that came from the database, so a
    ``FileField`` needs nothing but ``widget=FileChunkedUpload``. None of that
    was covered: these walk the three moments of the round trip -- saving a new
    file, reopening the record, and clearing it.
    """

    def submit(self):
        self.driver.find_element(
            By.CSS_SELECTOR, 'button[type=submit], input[type=submit]').click()

    def test_the_upload_is_saved_into_the_model_field(self):
        path = self.write_temp_file('memoria.txt', PAYLOAD)
        self.go('/chunkedupload/')
        self.driver.find_element(By.CSS_SELECTOR, '#id_name').send_keys('Alta')
        self.driver.find_element(By.CSS_SELECTOR, WIDGET).send_keys(path)
        self.wait_js(
            "return document.querySelector('input.chunkedvalue').value !== '';",
            message='the upload never finished')

        self.submit()

        self.wait.until(
            lambda d: ChunkedUploadItem.objects.filter(name='Alta').exists(),
            'the form never saved')
        item = ChunkedUploadItem.objects.get(name='Alta')
        with item.fileexample.open('rb') as stored:
            self.assertEqual(stored.read(), PAYLOAD,
                             'the model field did not get the uploaded bytes')

    def test_a_file_already_in_the_database_is_shown(self):
        item = ChunkedUploadItem(name='Con fichero')
        item.fileexample.save('informe.txt', ContentFile(b'previo'), save=True)

        self.go(f'/chunkedupload/{item.pk}')

        value = json.loads(self.js(
            "return document.querySelector('input.chunkedvalue').value;"))
        # Storage may have uniquified the name (informe_a1b2c3.txt); what
        # matters is that the widget shows the file the record actually has.
        stored_name = Path(item.fileexample.name).name
        self.assertEqual(value['display_name'], stored_name)
        self.assertIn(stored_name, value['url'])
        # The download link is only rendered for a file that exists.
        self.assertTrue(self.js(
            "const a = document.querySelector('[id^=download_] a');"
            "return a !== null && a.getAttribute('href') !== '';"),
            'no download link for the stored file')

    def test_saving_without_touching_it_keeps_the_file(self):
        item = ChunkedUploadItem(name='Intacto')
        item.fileexample.save('informe.txt', ContentFile(b'previo'), save=True)
        original = item.fileexample.name

        self.go(f'/chunkedupload/{item.pk}')
        self.submit()

        self.wait.until(lambda d: self._reloaded(item).fileexample.name == original,
                        'a save that touched nothing lost the file')

    def test_ticking_delete_clears_the_field(self):
        item = ChunkedUploadItem(name='Para borrar')
        item.fileexample.save('informe.txt', ContentFile(b'previo'), save=True)

        self.go(f'/chunkedupload/{item.pk}')
        self.driver.find_element(
            By.CSS_SELECTOR, '[id^=remove_] input[type=checkbox]').click()
        self.submit()

        self.wait.until(lambda d: not self._reloaded(item).fileexample.name,
                        'the file was not cleared')

    def _reloaded(self, item):
        return ChunkedUploadItem.objects.get(pk=item.pk)
