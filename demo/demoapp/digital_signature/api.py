"""
API view for serving digital signature documents as PDF files.

This view retrieves a DigitalSignature instance based on its primary key,
reads the associated PDF file from disk, and returns its binary content.
It is used to provide a preview of the document for digital signing.

Attributes:
    renderer_classes (list): A list of renderer classes to format the response.
                             Here, PDFRenderer is used to handle PDF output.
"""
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from rest_framework.generics import UpdateAPIView

from demoapp.digital_signature.serializers import DigitalSignatureSerializer
from demoapp.models import DigitalSignature
from djgentelella.firmador_digital.viewsets import DigitalSignatureRenderFileAPIView


@method_decorator(login_required, name='dispatch')
class DigitalSignatureFileAPIView(DigitalSignatureRenderFileAPIView):
    pass


class DigitalSignatureAPIUpdateTest(UpdateAPIView):
    queryset = DigitalSignature.objects.all()
    serializer_class = DigitalSignatureSerializer
