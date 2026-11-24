from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from djgentelella.chunked_upload.utils import find_upload
from djgentelella.firmador_digital.access import (
    VIEW,
    get_reference_instance,
    has_document_access,
    same_object,
)
from djgentelella.firmador_digital.consumers.pdf_render import PDFRenderer
from djgentelella.firmador_digital.forms import RenderValueForm


@method_decorator(login_required, name='dispatch')
class DigitalSignatureRenderFileAPIView(APIView):
    """
    The PDF the signature widget shows, for its preview.

    ``value`` is what the widget put in the page: a reference signed by the
    server or, after signing, the token of an upload of who asks. A value the
    client made up, a reference to another object than the one in the URL,
    an object that is gone and a user who may not see it all get the same
    404, so the answer does not tell whether the object exists.
    """
    renderer_classes = [PDFRenderer]

    form_class = RenderValueForm

    #: The object of the signed reference, once ``get`` has loaded it.
    document_instance = None
    #: The file field the signed reference names.
    document_field_name = None

    def check_user(self, cc, pk, user, token=None):
        """
        Whether ``user`` may see the document. A token is only read if
        ``user`` uploaded it (``get_file_from_token``); a reference asks
        :func:`~djgentelella.firmador_digital.access.has_document_access`,
        the rule the signing websocket uses too. Override it to change the
        rule of this endpoint only; ``FIRMADOR_ACCESS_CHECK`` changes both.
        """
        if token is not None:
            return True
        if self.document_instance is None:
            return False
        return has_document_access(user, self.document_instance,
                                   self.document_field_name, VIEW)

    def get_token_from_form(self, form):
        jsondata = form.cleaned_data['value']
        if 'token' in jsondata:
            return jsondata['token']
        return None

    def get_file_from_token(self, token):
        # Only a finished upload of who asks: the token alone would show
        # anyone's upload to any signed-in user.
        tmpupload = find_upload(token, self.request.user)
        dev = None
        if tmpupload:
            dev = tmpupload.get_uploaded_file()
        return dev

    def file_document(self, form, cc, pk):
        jsondata = form.cleaned_data['value']
        if 'field_name' in jsondata:
            return self.get_instance_file(self.document_instance,
                                          self.document_field_name)
        if 'token' in jsondata:
            return self.get_file_from_token(jsondata['token'])
        return None

    def not_found(self):
        return Response({'detail': _('File not found')},
                        status=status.HTTP_404_NOT_FOUND)

    def get(self, request, cc, pk, format=None):
        """
        Serve the PDF the widget references, as ``application/pdf``.

        Parameters:
            request (HttpRequest): The incoming HTTP request; ``value`` in
                its query string.
            cc (int): The content type the widget rendered the URL with.
            pk (int or str): The primary key the widget rendered the URL with.
            format (optional): The format specifier (default is None).

        Returns:
            Response: the PDF, or a 404 ``File not found``.
        """
        form = self.form_class(data=request.GET)
        if not form.is_valid():
            return self.not_found()
        jsondata = form.cleaned_data['value']
        if 'field_name' in jsondata:
            # The signed reference names the object, not the URL: they must
            # agree, and the object must still be there.
            if not same_object(jsondata, cc, pk):
                return self.not_found()
            self.document_instance = get_reference_instance(jsondata)
            self.document_field_name = jsondata['field_name']
            if self.document_instance is None:
                return self.not_found()
        token = self.get_token_from_form(form)
        if not self.check_user(cc, pk, request.user, token=token):
            return self.not_found()

        file_data = self.file_document(form, cc, pk)
        if file_data is None:
            # It used to answer 200 with the text 'None'.
            return self.not_found()
        return Response(file_data, content_type='application/pdf')

    def get_instance_file(self, instance, fieldname):
        # check if instance and fieldname are not None
        if not instance or not fieldname:
            return None

        file_path = getattr(instance, fieldname, None)
        if not file_path:
            return None

        # check if not file
        try:
            with open(file_path.path, 'rb') as f:
                file_data = f.read()

            return file_data
        except (FileNotFoundError, OSError):
            return None
