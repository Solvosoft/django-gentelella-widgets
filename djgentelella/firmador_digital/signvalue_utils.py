import logging

from djgentelella.chunked_upload.utils import ANY_USER, find_upload
from djgentelella.firmador_digital.access import (
    decode_document_value,
    get_reference_instance,
)

logger = logging.getLogger('djgentelella')


class ValueDSParser:

    def get_file_from_token(self, token):
        # A form widget (DigitalSignatureInput) does not see the request, so it
        # takes the upload whoever uploaded it, as the generic upload widgets
        # do; DigitalSignatureField (DRF) overrides this with the user.
        tmpupload = find_upload(token, ANY_USER)
        dev = None
        if tmpupload:
            dev = tmpupload.get_uploaded_file()
        return dev

    def get_json_file(self, value):
        """The value decoded: a reference signed by the server
        (``{contenttype, pk, field_name}``) or ``{token}``; ``None`` for
        anything else, an unsigned reference included."""
        return decode_document_value(value)

    def get_filefield(self, jsondata):
        if 'field_name' in jsondata:
            instance = get_reference_instance(jsondata)
            if instance is None:
                return None
            return self.get_instance_file(instance, jsondata['field_name'])
        if 'token' in jsondata:
            return self.get_file_from_token(jsondata['token'])
        return None

    def get_instance_file(self, instance, fieldname):
        file_path = getattr(instance, fieldname)
        return file_path
