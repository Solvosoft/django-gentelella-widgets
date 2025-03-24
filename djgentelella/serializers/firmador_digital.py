from django.apps import apps
from rest_framework import serializers
from django.db.models import FileField

class DocumentSettingsSerializer(serializers.Serializer):
    pageNumber = serializers.IntegerField(min_value=1, default=1)
    signWidth = serializers.IntegerField(min_value=1, default=133)
    signHeight = serializers.IntegerField(min_value=1, default=33)
    signX = serializers.IntegerField(min_value=0, default=198)
    signY = serializers.IntegerField(min_value=0, default=0)

class InstanceSerializer(serializers.Serializer):
    pk = serializers.IntegerField()
    model = serializers.CharField()
    app = serializers.CharField()
    field_name  = serializers.CharField()

    def validate(self, attrs):
        app_label = attrs.get("app")
        model_name = attrs.get("model")
        pk = attrs.get("pk")
        field_name = attrs.get("field_name")

        try:
            ModelClass = apps.get_model(app_label=app_label, model_name=model_name)
        except LookupError:
            raise serializers.ValidationError({"model": "Invalid model provided."})

        try:
            instance = ModelClass.objects.get(pk=pk)
        except ModelClass.DoesNotExist:
            raise serializers.ValidationError({"pk": "Instance not found."})

        if not hasattr(instance, field_name):
            raise serializers.ValidationError({
                "field_name": "The instance does not have field: %s" % field_name
            })

        field_obj = instance._meta.get_field(field_name)
        if not isinstance(field_obj, FileField):
            raise serializers.ValidationError({
                "field_name": "Field %s is not a FileField." % field_name
            })

        attrs["instance_obj"] = instance
        attrs["model_class"] = ModelClass
        attrs["field_name"] = field_name
        return attrs


class RequestInitialDoc(serializers.Serializer):
    docsettings = DocumentSettingsSerializer()

class WSRequest(serializers.Serializer):
    action = serializers.CharField()

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
    docsettings = DocumentSettingsSerializer()
    card = CardSerializer()
    logo_url = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    instance = InstanceSerializer()

    def validate(self, data):
        instance_data = data.pop('instance')
        data['instance'] = instance_data['instance_obj']
        data['model_class'] = instance_data['model_class']
        data['field_name'] = instance_data['field_name']

        return data

class CompleteSignatureSerializer(serializers.Serializer):
    action = serializers.CharField()
    documentid = serializers.CharField()
    certificate = serializers.CharField()
    signature = SignatureSerializer()
    logo_url = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    instance = InstanceSerializer()

    def validate(self, data):
        instance_data = data.pop('instance')
        data['instance'] = instance_data['instance_obj']
        data['model_class'] = instance_data['model_class']
        data['field_name'] = instance_data['field_name']

        return data
