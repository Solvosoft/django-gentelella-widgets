import base64

from django.core.files.base import ContentFile
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers


class GTBase64FileField(serializers.Field):
    def to_internal_value(self, data):
        if not isinstance(data, list):  # Verifica si es una lista
            raise serializers.ValidationError(_("A list was expected"))

        # Procesa cada elemento de la lista
        file_contents = []
        for item in data:
            required_fields = ["name", "value"]
            for field in required_fields:
                if field not in item:
                    raise serializers.ValidationError(
                        _("Invalid structure, each item should provide {name: 'name of file', value:'base64 string representation'}"))

            file_name = item["name"]
            file_value = item["value"]

            try:
                # Decodificar el contenido en base64
                decoded_value = base64.b64decode(file_value)
            except base64.binascii.Error:
                raise serializers.ValidationError(_(
                    f"The 'value' for file '{file_name}' is not a valid base64 string"))

            file_content = ContentFile(decoded_value, name=file_name)
            file_contents.append(file_content)

        return file_contents

    def to_representation(self, value):
        pass
