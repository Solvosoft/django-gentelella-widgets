"""Upload widgets: the user-scoped ones, the JSON of a stored file and the
``data-widget`` a subclass keeps."""
import json
from html import unescape

from django import forms
from django.contrib.auth.models import AnonymousUser, User
from django.core.files.base import ContentFile
from django.test import TestCase

from djgentelella.chunked_upload.constants import COMPLETE, UPLOADING
from djgentelella.forms.forms import GTForm, UserScopedUploadsMixin
from djgentelella.models import ChunkedUpload
from djgentelella.widgets import core as genwidgets
from djgentelella.widgets.files import FileChunkedUpload, UserFileChunkedUpload
from djgentelella.widgets.pdf import PDFViewerWidget
from djgentelella.widgets.tagging import TaggingInput
from djgentelella.widgets.trees import TreeSelect

# A file name may hold anything but a slash.
MALICIOUS = 'a"b\'c<\\script><img src=x onerror=alert(1)>&.txt'


class StoredFile:
    """What a FileField hands the widget: a name and a url."""

    def __init__(self, name, url):
        self.name = name
        self.url = url

    def __bool__(self):
        return True


class ProjectUpload(FileChunkedUpload):
    """A subclass written in a project, with no javascript of its own."""

    # This module is inside djgentelella; the subclass stands for one that
    # is not.
    __module__ = 'demoapp.widgets'


class ProjectTreeSelect(TreeSelect):
    __module__ = 'demoapp.widgets'


class OwnJavascriptUpload(FileChunkedUpload):
    js_widget = 'OwnJavascriptUpload'


class UploadForm(UserScopedUploadsMixin, GTForm):
    file = forms.FileField(widget=UserFileChunkedUpload, required=False)


class UploadsTestBase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='x')
        self.other = User.objects.create_user('other', password='x')
        self.uploads = []

    def tearDown(self):
        for upload in self.uploads:
            if ChunkedUpload.objects.filter(pk=upload.pk).exists():
                upload.delete()

    def upload(self, user, status=COMPLETE):
        upload = ChunkedUpload(user=user, filename='data.txt', status=status,
                               offset=4)
        upload.file.save('data.txt', ContentFile(b'data'), save=False)
        upload.save()
        self.uploads.append(upload)
        return upload

    @staticmethod
    def data(upload, name='file'):
        return {name: json.dumps({'token': upload.upload_id})}


class UserFileChunkedUploadTest(UploadsTestBase):
    def test_takes_a_finished_upload_of_its_user(self):
        upload = self.upload(self.owner)
        widget = UserFileChunkedUpload(user=self.owner)

        value = widget.value_from_datadict(self.data(upload), {}, 'file')

        self.assertEqual(value.name, 'data.txt')
        self.assertEqual(value.read(), b'data')
        value.close()
        self.assertFalse(ChunkedUpload.objects.filter(pk=upload.pk).exists())

    def test_the_token_of_another_user_gives_none_and_deletes_nothing(self):
        upload = self.upload(self.other)
        widget = UserFileChunkedUpload(user=self.owner)

        self.assertIsNone(widget.value_from_datadict(self.data(upload), {}, 'file'))
        self.assertTrue(ChunkedUpload.objects.filter(pk=upload.pk).exists())

    def test_an_unfinished_upload_gives_none_and_is_not_deleted(self):
        upload = self.upload(self.owner, status=UPLOADING)
        widget = UserFileChunkedUpload(user=self.owner)

        self.assertIsNone(widget.value_from_datadict(self.data(upload), {}, 'file'))
        self.assertTrue(ChunkedUpload.objects.filter(pk=upload.pk).exists())

    def test_without_a_user_nothing_is_taken(self):
        upload = self.upload(self.owner)
        for user in (None, AnonymousUser()):
            widget = UserFileChunkedUpload(user=user)
            self.assertIsNone(
                widget.value_from_datadict(self.data(upload), {}, 'file'))
        self.assertTrue(ChunkedUpload.objects.filter(pk=upload.pk).exists())

    def test_the_generic_widget_still_takes_the_upload_of_another_user(self):
        """On purpose: who attaches the file need not be who uploaded it."""
        upload = self.upload(self.other)
        widget = FileChunkedUpload()

        value = widget.value_from_datadict(self.data(upload), {}, 'file')

        self.assertEqual(value.name, 'data.txt')
        value.close()
        self.assertFalse(ChunkedUpload.objects.filter(pk=upload.pk).exists())

    def test_the_generic_file_input_still_takes_the_upload_of_another_user(self):
        upload = self.upload(self.other)
        value = genwidgets.FileInput().value_from_datadict(
            self.data(upload), {}, 'file')
        self.assertEqual(value.name, 'data.txt')
        value.close()

    def test_user_file_input_refuses_another_user(self):
        upload = self.upload(self.other)
        widget = genwidgets.UserFileInput(user=self.owner)
        self.assertIsNone(widget.value_from_datadict(self.data(upload), {}, 'file'))
        self.assertTrue(ChunkedUpload.objects.filter(pk=upload.pk).exists())
        mine = self.upload(self.owner)
        value = widget.value_from_datadict(self.data(mine), {}, 'file')
        self.assertEqual(value.name, 'data.txt')
        value.close()

    def test_the_delete_action_still_clears_the_field(self):
        widget = UserFileChunkedUpload(user=None)
        self.assertIs(widget.value_from_datadict(
            {'file': json.dumps({'actions': 'delete'})}, {}, 'file'), False)

    def test_garbage_gives_none(self):
        for widget in (FileChunkedUpload(), genwidgets.FileInput(),
                       UserFileChunkedUpload(user=self.owner)):
            for value in (None, '', 'not json', '"token"', '[1]', '{"token": 3}'):
                self.assertIsNone(
                    widget.value_from_datadict({'file': value}, {}, 'file'),
                    '%s %r' % (type(widget).__name__, value))

    def test_the_form_mixin_passes_the_user_of_the_request(self):
        mine, theirs = self.upload(self.owner), self.upload(self.other)

        class Request:
            user = self.owner

        form = UploadForm(self.data(theirs), request=Request())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data['file'])
        self.assertTrue(ChunkedUpload.objects.filter(pk=theirs.pk).exists())

        form = UploadForm(self.data(mine), user=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['file'].name, 'data.txt')
        form.cleaned_data['file'].close()

    def test_the_user_is_bound_per_form_instance(self):
        first = UploadForm(user=self.owner)
        second = UploadForm(user=self.other)
        self.assertIs(first.fields['file'].widget.user, self.owner)
        self.assertIs(second.fields['file'].widget.user, self.other)
        self.assertIsNone(UploadForm.base_fields['file'].widget.user)

    def test_a_form_that_keeps_its_own_user_binds_it_before_cleaning(self):
        # The form consumes ``user`` itself.
        class OwnUserForm(UserScopedUploadsMixin, GTForm):
            file = forms.Field(widget=UserFileChunkedUpload(keep_upload=True),
                               required=False)

            def __init__(self, *args, user=None, **kwargs):
                super().__init__(*args, **kwargs)
                self.user = user

        mine, theirs = self.upload(self.owner), self.upload(self.other)
        form = OwnUserForm(self.data(theirs), user=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data['file'])

        form = OwnUserForm(self.data(mine), user=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['file'], mine)

    def test_a_user_passed_on_by_the_form_reaches_the_mixin(self):
        class PassingForm(UserScopedUploadsMixin, GTForm):
            file = forms.FileField(widget=UserFileChunkedUpload, required=False)

            def __init__(self, *args, user=None, **kwargs):
                super().__init__(*args, user=user, **kwargs)
                self.owner = user

        form = PassingForm(user=self.owner)
        self.assertIs(form.fields['file'].widget.user, self.owner)

    def test_the_subwidgets_of_a_multiwidget_are_bound(self):
        class Pair(forms.MultiWidget):
            def __init__(self):
                super().__init__([UserFileChunkedUpload(), forms.TextInput()])

            def decompress(self, value):
                return [None, None]

        class PairForm(UserScopedUploadsMixin, GTForm):
            pair = forms.Field(widget=Pair, required=False)

        form = PairForm(user=self.owner)
        self.assertIs(form.fields['pair'].widget.widgets[0].user, self.owner)

    def test_keep_upload_gives_the_upload_and_does_not_delete_it(self):
        mine = self.upload(self.owner)
        widget = UserFileChunkedUpload(user=self.owner, keep_upload=True)
        self.assertEqual(widget.value_from_datadict(self.data(mine), {}, 'file'),
                         mine)
        self.assertTrue(ChunkedUpload.objects.filter(pk=mine.pk).exists())

        class KeepingInput(genwidgets.UserFileInput):
            keep_upload = True

        self.assertEqual(KeepingInput(user=self.owner).value_from_datadict(
            self.data(mine), {}, 'file'), mine)
        theirs = self.upload(self.other)
        self.assertIsNone(widget.value_from_datadict(self.data(theirs), {}, 'file'))

    def test_renders_with_the_javascript_of_the_generic_widget(self):
        html = str(UploadForm(user=self.owner)['file'])
        self.assertIn('data-widget="FileChunkedUpload"', html)
        self.assertIn('chunkedupload-input', html)
        self.assertIn('class="chunkedvalue"', html)


class FormatValueTest(TestCase):
    def test_a_malicious_name_is_valid_json_and_inert_html(self):
        stored = StoredFile('uploads/' + MALICIOUS,
                            '/media/</script><b>/' + MALICIOUS)
        widget = FileChunkedUpload()

        value = widget.format_value(stored)
        self.assertEqual(json.loads(value), {
            'name': 'uploads/' + MALICIOUS, 'display_name': MALICIOUS,
            'url': '/media/</script><b>/' + MALICIOUS})
        self.assertNotIn('<', value)
        self.assertNotIn('>', value)

        html = widget.render('file', stored)
        self.assertNotIn('<img', html)
        self.assertNotIn('</script>', html)
        self.assertNotIn('<b>', html)
        start = html.index('class="chunkedvalue"')
        attribute = html[start:].split("value='", 1)[1].split("'", 1)[0]
        # What the browser hands the javascript: the attribute, unescaped.
        self.assertEqual(json.loads(unescape(attribute))['display_name'],
                         MALICIOUS)

    def test_the_pdf_viewer_escapes_it_too(self):
        stored = StoredFile('docs/' + MALICIOUS, '/media/docs/x.pdf')
        html = PDFViewerWidget().render('pdf', stored)
        self.assertNotIn('<img', html)
        self.assertNotIn('</script>', html)

    def test_no_value_renders_empty(self):
        self.assertEqual(FileChunkedUpload().format_value(None), '')


class DataWidgetTest(TestCase):
    def test_a_project_subclass_keeps_the_name_of_its_base(self):
        self.assertEqual(ProjectUpload().attrs['data-widget'], 'FileChunkedUpload')
        self.assertEqual(ProjectTreeSelect().attrs['data-widget'], 'TreeSelect')

        class LocalInput(genwidgets.TextInput):
            __module__ = 'demoapp.widgets'

        self.assertEqual(LocalInput().attrs['data-widget'], 'TextInput')

    def test_the_widgets_of_djgentelella_keep_their_own_name(self):
        self.assertEqual(PDFViewerWidget().attrs['data-widget'], 'PDFViewerWidget')
        self.assertEqual(FileChunkedUpload().attrs['data-widget'],
                         'FileChunkedUpload')
        self.assertEqual(genwidgets.DateInput().attrs['data-widget'], 'DateInput')
        self.assertEqual(UserFileChunkedUpload().attrs['data-widget'],
                         'FileChunkedUpload')
        self.assertEqual(genwidgets.UserFileInput().attrs['data-widget'],
                         'FileInput')

    def test_a_project_subclass_also_renders_its_class_name(self):
        # Before js_widget, the data-widget of a subclass was its class name;
        # a project that registered javascript under it is still found by
        # the data-widget-class (widgets.js prefers it when registered).
        self.assertEqual(ProjectUpload().attrs['data-widget-class'], 'ProjectUpload')
        self.assertIn('data-widget-class="ProjectUpload"',
                      ProjectUpload().render('f', None))
        self.assertEqual(ProjectTreeSelect().attrs['data-widget-class'],
                         'ProjectTreeSelect')

        class LocalTagging(TaggingInput):
            __module__ = 'demoapp.widgets'

        self.assertEqual(LocalTagging().attrs['data-widget'], 'TaggingInput')
        self.assertEqual(LocalTagging().attrs['data-widget-class'], 'LocalTagging')

    def test_a_widget_named_as_its_class_renders_no_class_name(self):
        for widget in (FileChunkedUpload(), PDFViewerWidget(), TaggingInput(),
                       genwidgets.DateInput(), OwnJavascriptUpload()):
            self.assertNotIn('data-widget-class', widget.attrs, widget)

    def test_a_stale_class_name_in_the_attrs_is_dropped(self):
        attrs = genwidgets.update_kwargs({'data-widget-class': 'Old'}, 'TextInput')
        self.assertNotIn('data-widget-class', attrs)

    def test_js_widget_names_a_widget_with_javascript_of_its_own(self):
        self.assertEqual(OwnJavascriptUpload().attrs['data-widget'],
                         'OwnJavascriptUpload')
        self.assertEqual(genwidgets.js_widget_name(ProjectUpload),
                         'FileChunkedUpload')
