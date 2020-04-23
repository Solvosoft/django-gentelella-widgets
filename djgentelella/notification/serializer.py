from rest_framework.pagination import LimitOffsetPagination

from djgentelella.models import Notification
from rest_framework import serializers


class NotificationPagination(LimitOffsetPagination):
    default_limit = 5

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ('id', 'description', 'link', 'message_type', 'state', 'creation_date')

class NotificationSerializerUpdate(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ('state',)

