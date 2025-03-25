from rest_framework import serializers

from demoapp.models import DigitalSignature


class DigitalSignatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = DigitalSignature
        fields = ['file']
