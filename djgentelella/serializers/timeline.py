import datetime

from rest_framework import serializers


class MediaSerializer(serializers.Serializer):
    url = serializers.URLField()
    caption = serializers.CharField(required=False)
    credit = serializers.CharField(required=False)
    thumbnail = serializers.URLField(required=False)
    alt = serializers.CharField(required=False)
    title = serializers.CharField(required=False)
    link = serializers.URLField(required=False)
    link_target = serializers.CharField(required=False)


class TextSerializer(serializers.Serializer):
    headline = serializers.CharField()
    text = serializers.CharField()


class DateSerializer(serializers.BaseSerializer):
    def to_representation(self, obj):
        if isinstance(obj, datetime.date):
            return {'month': obj.month,
                    'day': obj.day,
                    'year': obj.year}
        if isinstance(obj, datetime.datetime):
            return {'month': obj.month,
                    'day': obj.day,
                    'year': obj.year,
                    'minute': obj.minute,
                    'second': obj.second,
                    'millisecond': obj.millisecond}
        return {'year': obj}


class SlideSerializer(serializers.Serializer):
    start_date = DateSerializer()
    end_date = DateSerializer(required=False)
    text = TextSerializer(required=False)
    media = MediaSerializer(required=False)
    group = serializers.CharField(required=False)
    display_date = serializers.CharField(required=False)
    background = serializers.CharField(required=False)
    autolink = serializers.BooleanField(default=True)
    unique_id = serializers.CharField(required=False)


class EraSerializer(serializers.Serializer):
    start_date = DateSerializer()
    end_date = DateSerializer()
    text = serializers.CharField()


class GTimelineBase(serializers.Serializer):
    """
    See: https://timeline.knightlab.com/docs/json-format.html#json-slide
    """

    title = SlideSerializer(required=False)
    events = SlideSerializer(many=True)
    scale = serializers.CharField(default='human')
    eras = EraSerializer(many=True)
