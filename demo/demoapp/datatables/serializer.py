from django_filters import DateFromToRangeFilter, DateTimeFromToRangeFilter
from django_filters import FilterSet
from rest_framework import serializers

from demoapp.models import Person, Country
from djgentelella.fields.drfdatetime import DateRangeTextWidget, DateTimeRangeTextWidget

from django.contrib.auth.models import User
from djgentelella.models import Notification


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


class UserSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = (
            'id',
            'username',
        )


class NotificationSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    creation_date = serializers.DateTimeField(format='%B %d, %Y %H:%M')
    # Possible format:
    # '%d de %B de %Y a las %H:%M'

    class Meta:
        model = Notification
        fields = (
            'message_type',
            'creation_date',
            'description',
            'link',
            'state',
            'user',
            'category',
            'update_date'
        )


class NotificationDataTableSerializer(serializers.Serializer):
    data = serializers.ListField(child=NotificationSerializer(), required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)
