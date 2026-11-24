import base64
import json
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from djgentelella.chunked_upload.utils import find_upload, request_user
from djgentelella.firmador_digital.access import same_object
from djgentelella.firmador_digital.signvalue_utils import ValueDSParser


class GTBase64FileField(serializers.FileField):
    def __init__(
        self,
        *args,
        max_files=1,
        delete_if_empty=False,
        allow_empty_file=False,
        **kwargs,
    ):
        self.max_files = max_files
        self.delete_if_empty = delete_if_empty
        self.allow_empty_file = allow_empty_file
        super().__init__(*args, **kwargs)

    def to_internal_value(self, datalist):
        result = []
        if not isinstance(datalist, list):
            raise serializers.ValidationError(
                _(
                    "A list of elements is expected, ej: [{name: 'name of "
                    "file', value:'base64 string representation'}]"
                )
            )
        if len(datalist) > self.max_files:
            raise serializers.ValidationError(
                _(f'Too many elements, max_file = {self.max_files}')
            )

        for data in datalist:
            required_fields = ['name', 'value']
            for field in required_fields:
                if field not in data:
                    raise serializers.ValidationError(
                        _(
                            "Invalid structure you need to provide {name: "
                            "'name of file', value:'base64 string "
                            "representation'}"
                        )
                    )
            name = slugify(Path(data['name']).stem)
            suffix = Path(data['name']).suffix
            file_name = name + suffix
            file_value = data['value']

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
    def parse_value(self, value):
        """
        Parses the given value and returns the parsed result.

        Args:
            value (str): The value to be parsed.

        Returns:
            The parsed result if the value is valid and contains the
            required attributes, one of url, token, or actions; otherwise
            returns None.
        """
        dev = None
        try:
            dev = json.loads(value)
            if not ('url' in dev or 'token' in dev or 'actions' in dev):
                dev = None
        except Exception as e:
            pass
        return dev

    def to_internal_value(self, data):
        """
        Converts the given data to internal value representation.

        Args:
            data (str): The data to be converted.

        Returns:
            The internal value representation of the data, or None if the
            data is invalid or does not contain the required attributes.
        """
        token = self.parse_value(data)
        dev = None
        if token:
            if 'actions' in token and token['actions'] == 'delete':
                return False
            if 'token' in token:
                # Only a finished upload of the user of the request: a token
                # is not enough to attach (and then read) someone else's file.
                tmpupload = find_upload(token['token'], request_user(self.context))
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
            return {'name': value.name, 'url': data, 'display_name': name}


class DigitalSignatureField(serializers.FileField, ValueDSParser):
    def get_file_from_token(self, token):
        """The file of a finished upload of the user of the request."""
        upload = find_upload(token, request_user(self.context))
        return upload.get_uploaded_file() if upload else None

    def to_internal_value(self, data):
        """
        Converts the given data to internal value representation.

        Args:
            data (str): The data to be converted.

        Returns:
            The internal value representation of the data, or None if the
            data is invalid or does not contain the required attributes.
        """
        dev = None
        jsondata = self.get_json_file(data)
        if jsondata:
            if 'field_name' in jsondata and not self.is_own_reference(jsondata):
                # A reference signed for another object or field: not a
                # way to copy a file the serializer was not given.
                return dev
            return self.get_filefield(jsondata)
        return dev

    def is_own_reference(self, reference):
        """Whether a signed reference names this field of the instance of
        the serializer."""
        instance = getattr(self.root, 'instance', None)
        if instance is None or isinstance(instance, (list, tuple)):
            return False
        return (reference['field_name'] == self.source
                and same_object(reference,
                                ContentType.objects.get_for_model(instance).pk,
                                instance.pk))

    def to_representation(self, value):
        data = super().to_representation(value)
        if data and value.name and value.storage.exists(value.name):
            name = Path(value.name).name
            return {'name': value.name, 'url': data, 'display_name': name}
