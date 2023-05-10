from django_filters import DateFromToRangeFilter, DateTimeFromToRangeFilter
from django_filters import FilterSet
from rest_framework import serializers

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

    class Meta:
        model = Person
        fields = "__all__"


class PersonDataTableSerializer(serializers.Serializer):
    data = serializers.ListField(child=PersonSerializer(), required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)
