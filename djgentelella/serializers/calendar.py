from rest_framework import serializers


class EventSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=255, required=False)
    groupId = serializers.CharField(max_length=255, required=False)
    start = serializers.DateTimeField(required=False)
    end = serializers.DateTimeField(required=False)
    daysOfWeek = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        required=False
    )
    startTime = serializers.TimeField(required=False)
    endTime = serializers.TimeField(required=False)
    startRecur = serializers.DateTimeField(required=False)
    endRecur = serializers.DateTimeField(required=False)
    title = serializers.CharField(max_length=255, required=False)
    url = serializers.URLField(required=False)
    interactive = serializers.BooleanField(required=False)
    className = serializers.CharField(max_length=255, required=False)
    classNames = serializers.ListField(
        child=serializers.CharField(max_length=255),
        required=False
    )
    editable = serializers.BooleanField(required=False)
    startEditable = serializers.BooleanField(required=False)
    durationEditable = serializers.BooleanField(required=False)
    resourceEditable = serializers.BooleanField(required=False)
    resourceId = serializers.CharField(max_length=255, required=False)
    resourceIds = serializers.ListField(
        child=serializers.CharField(max_length=255),
        required=False
    )
    display = serializers.ChoiceField(choices=[
        'auto',
        'block',
        'list-item',
        'background',
        'inverse-background',
        'none'
    ], required=False)
    overlap = serializers.BooleanField(required=False)
    constraint = serializers.CharField(max_length=255, required=False)
    color = serializers.CharField(max_length=255, required=False)
    backgroundColor = serializers.CharField(max_length=255, required=False)
    borderColor = serializers.CharField(max_length=255, required=False)
    textColor = serializers.CharField(max_length=255, required=False)
    extendedProps = serializers.JSONField(required=False)




