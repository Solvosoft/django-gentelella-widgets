"""
API view for serving digital signature documents as PDF files.

This view retrieves a DigitalSignature instance based on its primary key,
reads the associated PDF file from disk, and returns its binary content.
It is used to provide a preview of the document for digital signing.

Attributes:
    renderer_classes (list): A list of renderer classes to format the response.
                             Here, PDFRenderer is used to handle PDF output.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from demoapp.models import DigitalSignature
from djgentelella.firmador_digital.consumers.pdf_render import PDFRenderer


class DigitalSignatureFileAPIView(APIView):
    renderer_classes = [PDFRenderer]

    def get(self, request, pk, format=None):
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
        try:
            signature = DigitalSignature.objects.get(pk=pk)
        except DigitalSignature.DoesNotExist:
            return Response({"detail": "File not found"}, status=status.HTTP_404_NOT_FOUND)

        file_path = signature.file.path
        with open(file_path, 'rb') as f:
            file_data = f.read()

        return Response(file_data, content_type='application/pdf')
