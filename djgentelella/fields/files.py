import base64
from pathlib import Path

from django.core.files.base import ContentFile
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from djgentelella.models import ChunkedUpload


class GTBase64FileField(serializers.FileField):
    def __init__(self, *args, max_files=1, delete_if_empty=False,
                 allow_empty_file=False, **kwargs):
        self.max_files = max_files
        self.delete_if_empty = delete_if_empty
        self.allow_empty_file = allow_empty_file
        super().__init__(*args, **kwargs)

    def to_internal_value(self, datalist):
        result = []
        if not isinstance(datalist, list):
            raise serializers.ValidationError(
                _("A list of elements is expected, ej: [{name: 'name of file', value:'base64 string representation'}]"))
        if len(datalist) > self.max_files:
            raise serializers.ValidationError(
                _(f"Too many elements, max_file = {self.max_files}"))

        for data in datalist:
            required_fields = ["name", "value"]
            for field in required_fields:
                if field not in data:
                    raise serializers.ValidationError(
                        _("Invalid structure you need to provide {name: 'name of file', value:'base64 string representation'}"))
            name = slugify(Path(data["name"]).stem)
            suffix = Path(data["name"]).suffix
            file_name = name + suffix
            file_value = data["value"]

            try:
                # Decodificar el contenido en base64
                decoded_value = base64.b64decode(file_value)
            except base64.binascii.Error:
                self.fail('invalid')
                # raise serializers.ValidationError(_(
                #    "The 'value' is not a valid base64 string"))

            file_content = ContentFile(decoded_value, name=file_name)
            result.append(file_content)
        if result:
            if self.max_files == 1:
                return result[0]

            return result
        # here check for field of the instance
        if not self.delete_if_empty and self.root.instance:
            if hasattr(self.root.instance, self.source):
                return getattr(self.root.instance, self.source)
        if not self.allow_empty_file:
            self.fail('required')

    def to_representation(self, value):
        data = super().to_representation(value)
        if data and value.name and value.storage.exists(value.name):
            name = Path(value.name).name
            return {'name': name, 'url': data}


class ChunkedFileField(serializers.FileField):
    def to_internal_value(self, data):
        dev = None
        if data:
            tmpupload = ChunkedUpload.objects.filter(upload_id=data).first()
            if tmpupload:
                dev = tmpupload.get_uploaded_file()
                # tmpupload.delete()
            else:
                if self.root.instance:
                    if hasattr(self.root.instance, self.source):
                        return getattr(self.root.instance, self.source)
        return dev

    def to_representation(self, value):
        data = super().to_representation(value)
        if data and value.name and value.storage.exists(value.name):
            name = Path(value.name).name
            return {'name': name, 'url': data}
