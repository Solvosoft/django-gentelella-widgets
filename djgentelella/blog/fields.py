import base64
from django.core.files.base import ContentFile
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

class GTBase64FileField(serializers.Field):
    def to_internal_value(self, data):

        if not isinstance(data, list):
            raise serializers.ValidationError(_("List was expected"))


        if len(data) < 1:
            raise serializers.ValidationError(
                _("List must contain at least one element"))


        file_info = data[0]


        if not isinstance(file_info, dict) or 'name' not in file_info or 'value' not in file_info:
            raise serializers.ValidationError(
                _("Invalid structure. You need to provide {name: 'name of file', value: 'base64 string representation'}"))


        file_name = file_info['name']
        file_value = file_info['value']

        try:

            decoded_value = base64.b64decode(file_value)
        except base64.binascii.Error:
            raise serializers.ValidationError(_(
                "The 'value' is not a valid base64 string"))

        file_content = ContentFile(decoded_value, name=file_name)

        return file_content

    def to_representation(self, value):
        pass
