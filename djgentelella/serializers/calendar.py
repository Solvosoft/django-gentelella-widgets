from rest_framework import serializers


class EventSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
