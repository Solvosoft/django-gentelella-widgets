from rest_framework import serializers
from rest_framework.pagination import LimitOffsetPagination

from django.contrib.auth.models import User
from djgentelella.models import Notification
from django.utils import formats
from django_filters import FilterSet
from django_filters import DateTimeFromToRangeFilter
from djgentelella.fields.drfdatetime import DateTimeRangeTextWidget


class NotificationFilterSet(FilterSet):
    creation_date = DateTimeFromToRangeFilter(
        widget=DateTimeRangeTextWidget(
            attrs={'placeholder': formats.get_format('DATETIME_INPUT_FORMATS')[0]})
    )

    class Meta:
        model = Notification
        fields = {'message_type': ['icontains'], 'description': ['icontains'],
                  'link': ['icontains'], 'state': ['icontains']}


class UserSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = (
            'id',
            'username',
        )


class NotificationPagination(LimitOffsetPagination):
    default_limit = 5


class NotificationSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    creation_date = serializers.DateTimeField(format=formats.get_format('DATETIME_INPUT_FORMATS')[0])

    class Meta:
        model = Notification
        fields = (
            'id',
            'description',
            'link',
            'message_type',
            'state',
            'creation_date',
            'user'
        )


class NotificationSerializerUpdate(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ('state',)


class NotificationDataTableSerializer(serializers.Serializer):
    data = serializers.ListField(child=NotificationSerializer(), required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)
