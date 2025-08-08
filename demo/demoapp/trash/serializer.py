from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from demoapp.models import Customer

class CustomerSerializer(serializers.ModelSerializer):
    actions = serializers.SerializerMethodField()

    def get_actions(self, obj):
        return {
            "create": True,
            "update": True,
            "destroy": True,
        }

    class Meta:
        model = Customer
        fields = "__all__"


class CustomerDataTableSerializer(serializers.Serializer):
    data = serializers.ListField(child=CustomerSerializer(), required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)


class CustomerValidateSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        required=True, allow_blank=False, allow_null=False, max_length=150
    )
    email = serializers.EmailField(
        required=True, allow_blank=False, allow_null=False, max_length=100
    )
    phone_number = serializers.CharField(
        required=True, allow_blank=False, allow_null=False, max_length=100
    )

    class Meta:
        model = Customer
        fields = (
            "name",
            "email",
            "phone_number",
        )

