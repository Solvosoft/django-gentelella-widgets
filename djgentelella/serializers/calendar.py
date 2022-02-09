from rest_framework import serializers
from rest_framework.utils.serializer_helpers import BindingDict


class EventSerializer(serializers.Serializer):

    def __init__(self, data):
        fields = BindingDict(self)
        for key, value in self.get_fields().items():
            fields[key] = value
        if data:
            set1 = set(data[0].keys())
            set2 = set(fields)
            is_subset = set1.issubset(set2)
            if not is_subset:
                raise serializers.ValidationError("Serializer data is not accepted.")
        else:
            raise serializers.ValidationError("Empty event parameter.")
        super().__init__(self)

    id = serializers.CharField(max_length=255, required=False)
    groupId = serializers.CharField(max_length=255, required=False)
    allDay = serializers.BooleanField(required=False)
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

    def validate(self, data):
        """
        Check that start is before end.
        """
        date_values = {'start', 'end'}
        time_values = {'startTime', 'endTime'}
        if data:
            if date_values.issubset(set(data.keys())):
                if data['start'] > data['end']:
                    raise serializers.ValidationError("Event end date must occur after start date")
            if time_values.issubset(set(data.keys())):
                if data['startTime'] > data['endTime']:
                    raise serializers.ValidationError("Event end date must occur after start date")
        return data





