from rest_framework import serializers


class GTEncryptedTextField(serializers.CharField):
    def to_representation(self, value):
        if not value:
            return ""
        return str(value.decode())
