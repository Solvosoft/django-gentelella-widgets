"""Who is allowed to upload.

``ChunkedUploadBaseView`` used to refuse every anonymous request with a 403
baked into the view, so a public form with a file on it could not work at all
and there was nothing to override short of rewriting ``check_permissions``.
``login_required`` is that switch. It stays True by default: an upload endpoint
open to anyone is somewhere to park arbitrary files.
"""

from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase

from djgentelella.chunked_upload.views import ChunkedUploadView
from djgentelella.models import ChunkedUpload

CHUNK = b'the first hundred bytes, or fewer'


class PublicChunkedUploadView(ChunkedUploadView):
    """What a project writes to accept uploads from a form nobody logs into."""

    login_required = False


class ChunkedUploadPermissionsTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def post(self, view, user):
        request = self.factory.post(
            '/djgentelella/upload/',
            {'file': SimpleUploadedFile('demo.txt', CHUNK)},
            HTTP_CONTENT_RANGE='bytes 0-%d/%d' % (len(CHUNK) - 1, len(CHUNK)),
        )
        request.user = user
        return view.as_view()(request)

    def test_anonymous_is_refused_by_default(self):
        response = self.post(ChunkedUploadView, AnonymousUser())

        self.assertEqual(response.status_code, 403)
        self.assertFalse(ChunkedUpload.objects.exists(),
                         'a refused upload still created a row')

    def test_a_view_that_opts_out_accepts_anonymous(self):
        response = self.post(PublicChunkedUploadView, AnonymousUser())

        self.assertEqual(response.status_code, 200)
        upload = ChunkedUpload.objects.get()
        self.assertEqual(upload.offset, len(CHUNK))
        # Nothing to attach it to, and the model allows that.
        self.assertIsNone(upload.user)

    def test_the_default_is_still_login_required(self):
        """A project that never heard of the flag keeps the strict behaviour."""
        self.assertTrue(ChunkedUploadView.login_required)
