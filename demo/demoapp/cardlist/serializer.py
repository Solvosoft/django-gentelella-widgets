from django.utils import formats
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from demoapp.models import Person, Country
from djgentelella.serializers import GTDateField, GTDateTimeField


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = "__all__"


class PersonSerializer(serializers.ModelSerializer):
    country = CountrySerializer()
    actions = serializers.SerializerMethodField()

    def get_actions(self, obj):
        return {
            'do': True
        }

    class Meta:
        model = Person
        fields = "__all__"


class PersonCardListSerializer(serializers.Serializer):
    data = PersonSerializer(many=True)  # Enviar datos estructurados
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)


class PersonCreateSerializer(serializers.ModelSerializer):
    born_date = GTDateField()
    # also can overwrite input_formats and format
    last_time = GTDateTimeField(
        allow_empty_str=True,
        # True it is  default value  allow "" as none and prevent validation error
        input_formats=[formats.get_format('DATETIME_INPUT_FORMATS')[0]],
        format=formats.get_format('DATETIME_INPUT_FORMATS')[0])

    def validate_num_children(self, value):
        num_children = value
        if num_children < 0:
            raise ValidationError(detail=_("Value has to be positive or zero "))
        return num_children

    class Meta:
        model = Person
        fields = "__all__"


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = '__all__'


class PersonUpdateSerializer(serializers.ModelSerializer):
    born_date = GTDateField()
    last_time = GTDateTimeField()
    country = CountrySerializer()

    class Meta:
        model = Person
        fields = "__all__"
