import base64
import json
import logging

from rest_framework import serializers

logger = logging.getLogger('djgentelella')


class DocumentSettingsSerializer(serializers.Serializer):
    pageNumber = serializers.IntegerField(min_value=1, default=1)
    signWidth = serializers.IntegerField(min_value=1, default=133)
    signHeight = serializers.IntegerField(min_value=1, default=33)
    signX = serializers.IntegerField(min_value=0, default=198)
    signY = serializers.IntegerField(min_value=0, default=0)


class InstanceSerializer(serializers.Serializer):
    pk = serializers.IntegerField()
    cc = serializers.IntegerField()
    value = serializers.CharField()

    def get_json_file(self, value):
        jsondata = None
        try:
            instance = base64.b64decode(value.encode())
            jsondata = json.loads(instance.decode())
        except Exception as e:
            logger.error("Validation of value on digital signature fail", exc_info=e)
        return jsondata

    def get_file_from_token(self, token):
        from djgentelella.models import ChunkedUpload
        tmpupload = ChunkedUpload.objects.filter(upload_id=token).first()
        dev = None
        if tmpupload:
            dev = tmpupload.get_uploaded_file().read()
        return dev

    def get_instance_file(self, instance, fieldname):
        file_path = getattr(instance, fieldname)
        file_data = None
        with open(file_path.path, 'rb') as f:
            file_data = f.read()
        return file_data

    def validate_value(self, data):
        jsonparse = self.get_json_file(data)
        if not jsonparse:
            raise serializers.ValidationError("Invalid encode value")
        return jsonparse

    def validate(self, attrs):
        from django.contrib.contenttypes.models import ContentType
        cc = attrs.get("cc")
        pk = attrs.get("pk")
        ccinstance = ContentType.objects.get_for_id(cc)
        instance = ccinstance.get_object_for_this_type(pk=pk)
        value = attrs.get("value")
        if 'token' in value:
            attrs['value'] = self.get_file_from_token(value['token'])
        elif 'field_name' in value:
            attrs['value'] = self.get_instance_file(instance, value['field_name'])
        return attrs


class RequestInitialDoc(serializers.Serializer):
    docsettings = DocumentSettingsSerializer()


class WSRequest(serializers.Serializer):
    action = serializers.CharField(required=True)
    socket_id = serializers.CharField(required=True)


class CardSerializer(serializers.Serializer):
    certificate = serializers.CharField()
    commonName = serializers.CharField()
    firstName = serializers.CharField()
    identification = serializers.CharField()
    lastName = serializers.CharField()
    tokenSerialNumber = serializers.CharField()


class SignatureSerializer(serializers.Serializer):
    algorithm = serializers.CharField()
    value = serializers.CharField()


class InitialSignatureSerializer(serializers.Serializer):
    action = serializers.CharField()
    socket_id = serializers.CharField(required=True)
    docsettings = DocumentSettingsSerializer()
    card = CardSerializer()
    logo_url = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    instance = InstanceSerializer()


class CompleteSignatureSerializer(serializers.Serializer):
    action = serializers.CharField()
    socket_id = serializers.CharField(required=True)
    documentid = serializers.CharField()
    certificate = serializers.CharField()
    signature = SignatureSerializer()
    logo_url = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    instance = InstanceSerializer()

class ValidateDocumentSerializer(serializers.Serializer):
    action = serializers.CharField()
    socket_id = serializers.CharField(required=True)
    instance = InstanceSerializer()
