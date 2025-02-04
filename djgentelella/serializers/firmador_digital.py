from rest_framework import serializers


class DocumentSettingsSerializer(serializers.Serializer):
    pageNumber = serializers.IntegerField(min_value=1, default=1)
    signWidth = serializers.IntegerField(min_value=1, default=133)
    signHeight = serializers.IntegerField(min_value=1, default=33)
    signX = serializers.IntegerField(min_value=0, default=198)
    signY = serializers.IntegerField(min_value=0, default=0)


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


# class TestFlowPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
#     def get_queryset(self):
#         from controlsample.models import TestFlow
#
#         return TestFlow.objects.all()


# class OrganizationPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
#     def get_queryset(self):
#         from corebase.models import Organization
#
#         return Organization.objects.all()


class InitialSignatureSerializer(serializers.Serializer):
    action = serializers.CharField()
    docsettings = DocumentSettingsSerializer()
    # organization = OrganizationPrimaryKeyRelatedField(queryset=None)
    # instance = TestFlowPrimaryKeyRelatedField(queryset=None)
    card = CardSerializer()


class SignatureSerializer(serializers.Serializer):
    algorithm = serializers.CharField()
    value = serializers.CharField()


class CompleteSignatureSerializer(serializers.Serializer):
    action = serializers.CharField()
    documentid = serializers.CharField()
    certificate = serializers.CharField()
    # organization = OrganizationPrimaryKeyRelatedField(queryset=None)
    # instance = TestFlowPrimaryKeyRelatedField(queryset=None)
    signature = SignatureSerializer()
