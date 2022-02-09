from rest_framework import serializers


class TypeSerializer(serializers.Serializer):
    type = serializers.CharField(default='overview')


class BackgroundSerializer(serializers.Serializer):
    url = serializers.CharField(required=False)
    color = serializers.CharField(required=False)
    opacity = serializers.IntegerField(required=False)


class LocationSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    zoom = serializers.IntegerField(required=False)
    line = serializers.BooleanField(required=False)
    lat = serializers.DecimalField(max_digits=8, decimal_places=4, required=False)
    lon = serializers.DecimalField(max_digits=8, decimal_places=4, required=False)


class TextSerializer(serializers.Serializer):
    headline = serializers.CharField()
    text = serializers.CharField()


class MediaSerializer(serializers.Serializer):
    url = serializers.CharField(required=False)
    caption = serializers.CharField(required=False)
    credit = serializers.CharField(required=False)


class SlideSerializer(serializers.Serializer):
    type = TypeSerializer(required=False)
    date = serializers.CharField(required=False)
    location = LocationSerializer(required=False)
    background = BackgroundSerializer(required=False)
    text = TextSerializer(required=False)
    media = MediaSerializer(required=False)


class ZoomifySerializer(serializers.Serializer):
    attribution = serializers.CharField(required=False)
    path = serializers.CharField(required=True)
    width = serializers.IntegerField(required=True)
    height = serializers.IntegerField(required=True)
    tolerance = serializers.DecimalField(required=True, max_digits=8, decimal_places=4)


class StoryMapMBSerializer(serializers.Serializer):
    """ Map based story map"""
    language = serializers.CharField(required=False)
    map_type = serializers.CharField(required=False)
    map_as_image = serializers.BooleanField(required=False)
    map_subdomains = serializers.CharField(required=False)
    slides = SlideSerializer(many=True)


class StoryMapGPSerializer(serializers.Serializer):
    """ Giga pixel story map"""
    language = serializers.CharField(required=False)
    map_type = serializers.CharField(default='zoomify')
    map_as_image = serializers.BooleanField(required=False)
    map_background_color = serializers.CharField(required=False)
    zoomify = ZoomifySerializer(required=True)
    slides = SlideSerializer(many=True)


class GStoryMapMBSerializer(serializers.Serializer):
    """ Map based story map"""
    storymap = StoryMapMBSerializer()


class GStoryMapGPSerializer(serializers.Serializer):
    """ Giga pixel story map"""
    font_css = serializers.CharField(required=False)
    storymap = StoryMapGPSerializer()
