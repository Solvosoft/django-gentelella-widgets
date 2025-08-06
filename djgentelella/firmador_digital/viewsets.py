from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from djgentelella.firmador_digital.consumers.pdf_render import PDFRenderer
from djgentelella.firmador_digital.forms import RenderValueForm
from djgentelella.models import ChunkedUpload


@method_decorator(login_required, name='dispatch')
class DigitalSignatureRenderFileAPIView(APIView):
    renderer_classes = [PDFRenderer]

    form_class = RenderValueForm

    def check_user(self, cc, pk, user, token=None):
        return True

    def get_token_from_form(self, form):
        jsondata = form.cleaned_data['value']
        if 'token' in jsondata:
            return jsondata['token']
        return None

    def get_file_from_token(self, token):
        tmpupload = ChunkedUpload.objects.filter(upload_id=token).first()
        dev = None
        if tmpupload:
            dev = tmpupload.get_uploaded_file()
        return dev

    def file_document(self, form, cc, pk):
        jsondata = form.cleaned_data['value']
        if 'field_name' in jsondata:
            ccinstance = ContentType.objects.get_for_id(cc)
            instance = ccinstance.get_object_for_this_type(pk=pk)
            return self.get_instance_file(instance, jsondata['field_name'])
        if 'token' in jsondata:
            return self.get_file_from_token(jsondata['token'])
        return None

    def get(self, request, cc, pk, format=None):
        """
        Retrieve and serve the PDF file associated with a DigitalSignature instance.

        Parameters:
            request (HttpRequest): The incoming HTTP request.
            pk (int or str): The primary key of the DigitalSignature instance.
            format (optional): The format specifier (default is None).

        Returns:
            Response: An HTTP response containing the PDF file data with the
                      content type 'application/pdf'. If the DigitalSignature instance
                      is not found, returns a 404 Not Found response.
        """
        form = self.form_class(data=request.GET)
        if not form.is_valid():
            return Response({"detail": "File not found"},
                            status=status.HTTP_404_NOT_FOUND)
        token = self.get_token_from_form(form)
        if not self.check_user(cc, pk, request.user, token=token):
            return Response({"detail": "File not found"},
                            status=status.HTTP_403_FORBIDDEN)

        file_data = self.file_document(form, cc, pk)

        return Response(file_data, content_type='application/pdf')

    def get_instance_file(self, instance, fieldname):
        # check if instance and fieldname are not None
        if not instance or not fieldname:
            return None

        file_path = getattr(instance, fieldname)
        if not file_path:
            return None

        # check if not file
        try:
            with open(file_path.path, 'rb') as f:
                file_data = f.read()

            return file_data
        except (FileNotFoundError, OSError):
            return None
