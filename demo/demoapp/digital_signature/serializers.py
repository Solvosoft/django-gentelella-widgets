from rest_framework import serializers

from demoapp.models import DigitalSignature
from djgentelella.fields.files import DigitalSignatureField


class DigitalSignatureSerializer(serializers.ModelSerializer):
    file = DigitalSignatureField()
    
    class Meta:
        model = DigitalSignature
        fields = ['file']
