from django.utils import formats
from django.utils.translation import gettext_lazy as _
from django_filters import DateFromToRangeFilter, DateTimeFromToRangeFilter
from django_filters import FilterSet
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from demoapp.models import Person, Country
from djgentelella.fields.drfdatetime import DateRangeTextWidget, DateTimeRangeTextWidget


class PersonFilterSet(FilterSet):
    born_date = DateFromToRangeFilter(
        widget=DateRangeTextWidget(attrs={'placeholder': 'YYYY/MM/DD'}))
    last_time = DateTimeFromToRangeFilter(
        widget=DateTimeRangeTextWidget(attrs={'placeholder': 'YYYY/MM/DD HH:MM:SS'}))

    class Meta:
        model = Person
        fields = {'name': ['icontains'], 'num_children': ['exact'],
                  'country__name': ['icontains']}


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


class PersonDataTableSerializer(serializers.Serializer):
    data = serializers.ListField(child=PersonSerializer(), required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)


class PersonCreateSerializer(serializers.ModelSerializer):
    born_date = serializers.DateField(
        input_formats=[formats.get_format('DATE_INPUT_FORMATS')[0]],
        format=formats.get_format('DATE_INPUT_FORMATS')[0])
    last_time = serializers.DateTimeField(
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
    born_date = serializers.DateField(
        input_formats=[formats.get_format('DATE_INPUT_FORMATS')[0]],
        format=formats.get_format('DATE_INPUT_FORMATS')[0])
    last_time = serializers.DateTimeField(
        input_formats=[formats.get_format('DATETIME_INPUT_FORMATS')[0]],
        format=formats.get_format('DATETIME_INPUT_FORMATS')[0])
    country = CountrySerializer()

    class Meta:
        model = Person
        fields = "__all__"
