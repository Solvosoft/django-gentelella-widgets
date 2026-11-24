"""
The digital signature form widget only changes the file of its own object
(W19).

``DigitalSignatureInput`` does not see the instance of its form. Before, it
turned any reference signed by the server into that object's file, so the
reference of object X, posted in the form of object Y, copied X's file into
Y. Now a reference means "unchanged" and the form keeps its initial value,
which a ``ModelForm`` takes from its own instance; only the token of a
signed copy changes the file.
"""
import base64
import json

from django import forms
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.forms import modelformset_factory
from django.test import TestCase

from demoapp.digital_signature.forms import DigitalSignatureForm
from demoapp.models import DigitalSignature
from djgentelella.chunked_upload.constants import COMPLETE
from djgentelella.firmador_digital import access
from djgentelella.models import ChunkedUpload
from djgentelella.widgets.digital_signature import DigitalSignatureInput


def b64(data):
    return base64.b64encode(json.dumps(data).encode()).decode()


class SignatureFormTargetTests(TestCase):
    def setUp(self):
        self.x = self.document('x-secret.pdf', b'%PDF-1.4 X')
        self.y = self.document('y-mine.pdf', b'%PDF-1.4 Y')
        self.x_name, self.y_name = self.x.file.name, self.y.file.name

    def document(self, name, content):
        doc = DigitalSignature(filename=name)
        doc.file.save(name, ContentFile(content), save=True)
        self.addCleanup(doc.file.delete, save=False)
        return doc

    def reference(self, doc):
        return access.sign_document_reference(doc, 'file')

    def save(self, instance, value):
        form = DigitalSignatureForm(data={'file': value}, files={},
                                    instance=instance)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        instance.refresh_from_db()
        return form

    def test_the_reference_of_another_object_copies_nothing(self):
        # The reproduction: on 73140ca0 Y ended up with the file of X.
        self.save(self.y, self.reference(self.x))
        self.assertEqual(self.y.file.name, self.y_name)
        self.x.refresh_from_db()
        self.assertEqual(self.x.file.name, self.x_name)

    def test_another_field_of_the_same_object_copies_nothing(self):
        self.save(self.y, access.sign_document_reference(self.y, 'filename'))
        self.assertEqual(self.y.file.name, self.y_name)

    def test_its_own_reference_keeps_its_file(self):
        form = self.save(self.y, self.reference(self.y))
        self.assertEqual(self.y.file.name, self.y_name)
        self.assertFalse(form.has_changed())

    def test_a_formset_keeps_each_file_in_its_object(self):
        formset_class = modelformset_factory(
            DigitalSignature, form=DigitalSignatureForm, extra=0)
        queryset = DigitalSignature.objects.filter(
            pk__in=[self.x.pk, self.y.pk]).order_by('pk')
        # The references swapped between the two forms.
        data = {'form-TOTAL_FORMS': '2', 'form-INITIAL_FORMS': '2',
                'form-0-id': str(self.x.pk), 'form-0-file': self.reference(self.y),
                'form-1-id': str(self.y.pk), 'form-1-file': self.reference(self.x)}
        formset = formset_class(data, queryset=queryset)
        self.assertTrue(formset.is_valid(), formset.errors)
        formset.save()
        self.x.refresh_from_db()
        self.y.refresh_from_db()
        self.assertEqual(self.x.file.name, self.x_name)
        self.assertEqual(self.y.file.name, self.y_name)

    def test_without_an_instance_a_reference_is_no_file(self):
        form = DigitalSignatureForm(data={'file': self.reference(self.x)}, files={})
        self.assertFalse(form.is_valid())
        self.assertIn('file', form.errors)

    def test_a_plain_form_keeps_its_initial(self):
        class PlainForm(forms.Form):
            file = forms.FileField(widget=DigitalSignatureInput(
                render_basename='digital_signature_file_api'))

        form = PlainForm(data={'file': self.reference(self.x)}, files={},
                         initial={'file': self.y.file})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['file'].name, self.y_name)

    def test_the_token_of_a_signed_copy_changes_the_file(self):
        upload = ChunkedUpload(user=User.objects.create_user('signer'),
                               filename='signed.pdf', status=COMPLETE, offset=4)
        upload.file.save('signed.pdf', ContentFile(b'%PDF-1.4 signed'), save=False)
        upload.save()
        self.addCleanup(upload.delete)
        self.save(self.y, b64({'token': upload.upload_id}))
        self.addCleanup(self.y.file.delete, save=False)
        self.assertNotEqual(self.y.file.name, self.y_name)
        with self.y.file.open('rb') as signed:
            self.assertEqual(signed.read(), b'%PDF-1.4 signed')
