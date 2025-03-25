import base64
import json
import logging

from django.contrib.contenttypes.models import ContentType

from djgentelella.models import ChunkedUpload

logger = logging.getLogger("djgentelella")


class ValueDSParser:

    def get_file_from_token(self, token):
        tmpupload = ChunkedUpload.objects.filter(upload_id=token).first()
        dev = None
        if tmpupload:
            dev = tmpupload.get_uploaded_file()
        return dev

    def get_json_file(self, value):
        jsondata = None
        try:
            instance = base64.b64decode(value.encode())
            jsondata = json.loads(instance.decode())
        except Exception as e:
            logger.error("Validation of value on digital signature fail", exc_info=e)
        return jsondata

    def get_filefield(self, jsondata):
        if 'field_name' in jsondata:
            ccinstance = ContentType.objects.get_for_id(jsondata['contenttype'])
            instance = ccinstance.get_object_for_this_type(pk=jsondata['pk'])
            return self.get_instance_file(instance, jsondata['field_name'])
        if 'token' in jsondata:
            return self.get_file_from_token(jsondata['token'])
        return None

    def get_instance_file(self, instance, fieldname):
        file_path = getattr(instance, fieldname)
        return file_path
