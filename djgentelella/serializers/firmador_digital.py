import logging

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from djgentelella.chunked_upload.utils import ANY_USER, find_upload, request_user
from djgentelella.firmador_digital.access import (
    SIGN,
    decode_document_value,
    get_reference_instance,
    has_document_access,
    same_object,
)

logger = logging.getLogger('djgentelella')


class DocumentSettingsSerializer(serializers.Serializer):
    pageNumber = serializers.IntegerField(min_value=1, default=1)
    signWidth = serializers.IntegerField(min_value=1, default=133)
    signHeight = serializers.IntegerField(min_value=1, default=33)
    signX = serializers.IntegerField(min_value=0, default=198)
    signY = serializers.IntegerField(min_value=0, default=0)


class InstanceSerializer(serializers.Serializer):
    """
    The document the signing websocket works on.

    ``value`` is a reference signed by the server (it must name the same
    ``cc``/``pk``) or the token of an upload of the user of the socket. With a
    reference, the user in the context (``user`` or ``request``) must pass
    :func:`~djgentelella.firmador_digital.access.has_document_access` for the
    ``action`` of the context (``sign`` by default), the same rule as the
    preview endpoint.
    """
    pk = serializers.IntegerField()
    cc = serializers.IntegerField()
    value = serializers.CharField()

    default_error_messages = {
        'invalid_value': _('Invalid encode value'),
        # One message for a reference to another object, an object that is
        # gone and a user who may not use it: it does not say which.
        'not_available': _('The document is not available.'),
    }

    def get_json_file(self, value):
        return decode_document_value(value)

    def get_file_from_token(self, token):
        # The signing consumer passes its user in the context: only a finished
        # upload of that user is signed.
        tmpupload = find_upload(token, request_user(self.context))
        dev = None
        if tmpupload:
            dev = tmpupload.get_uploaded_file().read()
        return dev

    def get_instance_file(self, instance, fieldname):
        file_path = getattr(instance, fieldname, None)
        if not file_path:
            return None
        try:
            with open(file_path.path, 'rb') as f:
                return f.read()
        except (FileNotFoundError, OSError):
            return None

    def get_user(self):
        user = request_user(self.context)
        return None if user is ANY_USER else user

    def validate_value(self, data):
        jsonparse = self.get_json_file(data)
        if not jsonparse:
            self.fail('invalid_value')
        return jsonparse

    def validate(self, attrs):
        value = attrs.get('value')
        if 'token' in value:
            attrs['value'] = self.get_file_from_token(value['token'])
            return attrs
        if not same_object(value, attrs.get('cc'), attrs.get('pk')):
            self.fail('not_available')
        instance = get_reference_instance(value)
        if instance is None or not has_document_access(
                self.get_user(), instance, value['field_name'],
                self.context.get('action', SIGN)):
            self.fail('not_available')
        data = self.get_instance_file(instance, value['field_name'])
        if data is None:
            self.fail('not_available')
        attrs['value'] = data
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
