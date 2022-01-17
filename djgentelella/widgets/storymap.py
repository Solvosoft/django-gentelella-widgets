from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet


class TypeSerializer(serializers.Serializer):
    type = serializers.CharField(default='overview')


class LocationSerializer(serializers.Serializer):
    lat = serializers.DecimalField()
    lon = serializers.DecimalField()


class TextSerializer(serializers.Serializer):
    headline = serializers.CharField()
    text = serializers.CharField()


class MediaSerializer(serializers.Serializer):
    url = serializers.URLField()
    caption = serializers.CharField(required=False)
    credit = serializers.CharField(required=False)


class SlideSerializer(serializers.Serializer):
    type = TypeSerializer(required=False)
    location = LocationSerializer(required=False)
    text = TextSerializer(required=False)
    media = MediaSerializer(required=False)


class ZoomifySerializer(serializers.Serializer):
    path = serializers.CharField(required=True)
    width = serializers.IntegerField(required=True)
    height = serializers.IntegerField(required=True)
    tolerance = serializers.DecimalField(required=True)


class StoryMapMBSerializer(serializers.Serializer):
    """ Map based story map"""
    language = serializers.CharField(required=True)
    map_type = serializers.CharField(required=True)
    map_as_image = serializers.BooleanField(required=True)
    map_subdomains = serializers.CharField(required=False)
    slides = SlideSerializer(many=True)


class StoryMapGPSerializer(serializers.Serializer):
    """ Giga pixel story map"""
    language = serializers.CharField(required=True)
    map_type = serializers.CharField(default='zoomify')
    map_as_image = serializers.BooleanField(required=True)
    map_background_color = serializers.CharField(required=False)
    zoomify = ZoomifySerializer()
    slides = SlideSerializer(many=True)


class GStoryMapMBSerializer(serializers.Serializer):
    width = serializers.IntegerField(required=True)
    height = serializers.IntegerField(required=True)
    font_css = serializers.CharField(required=False)
    calculate_zoom = serializers.BooleanField(default=True)
    storymap = StoryMapMBSerializer()


class GStoryMapGPSerializer(serializers.Serializer):
    width = serializers.IntegerField(required=True)
    height = serializers.IntegerField(required=True)
    font_css = serializers.CharField(required=False)
    calculate_zoom = serializers.BooleanField(default=True)
    storymap = StoryMapGPSerializer()


class BaseStoryMapGPView(ViewSet):
    serializer = GStoryMapGPSerializer

    def get_width(self):
        pass

    def get_height(self):
        pass

    def get_font_css(self):
        pass

    def get_calculate_zoom(self):
        pass

    def get_storymap(self):
        pass

    def get_serializer(self, data):
        return self.serializer(data)

    def list(self, request, format=None):
        self.request = request
        response = {
            'width': self.get_width(),
            'height': self.get_height(),
            'font_css': self.get_font_css(),
            'calculated_zoom': self.get_calculate_zoom(),
            'storymap': self.get_storymap()
        }
        return Response(self.get_serializer(response).data)


class BaseStoryMapGPView(ViewSet):
    serializer = GStoryMapMBSerializer

    def get_width(self):
        pass

    def get_height(self):
        pass

    def get_font_css(self):
        pass

    def get_calculate_zoom(self):
        pass

    def get_storymap(self):
        pass

    def get_serializer(self, data):
        return self.serializer(data)

    def list(self, request, format=None):
        self.request = request
        response = {
            'width': self.get_width(),
            'height': self.get_height(),
            'font_css': self.get_font_css(),
            'calculated_zoom': self.get_calculate_zoom(),
            'storymap': self.get_storymap()
        }
        return Response(self.get_serializer(response).data)
