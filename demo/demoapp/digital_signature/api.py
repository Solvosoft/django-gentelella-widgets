from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from demoapp.models import DigitalSignature
from djgentelella.firmador_digital.consumers.pdf_render import PDFRenderer


class DigitalSignatureFileAPIView(APIView):
    renderer_classes = [PDFRenderer]

    def get(self, request, pk, format=None):
        try:
            signature = DigitalSignature.objects.get(pk=pk)
        except DigitalSignature.DoesNotExist:
            return Response({"detail": "File not found"}, status=status.HTTP_404_NOT_FOUND)

        file_path = signature.file.path
        with open(file_path, 'rb') as f:
            file_data = f.read()

        return Response(file_data, content_type='application/pdf')
