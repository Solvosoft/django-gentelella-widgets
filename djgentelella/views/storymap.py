from django.http import JsonResponse
from rest_framework.viewsets import ViewSet

from djgentelella.serializers.storymap import GStoryMapMBSerializer, GStoryMapGPSerializer


class BaseStoryMapMBView(ViewSet):
    serializer = GStoryMapMBSerializer

    def get_storymap(self):
        pass

    def get_serializer(self, data):
        return self.serializer(data)

    def list(self, request, format=None):
        self.request = request
        response = {
            "storymap": self.get_storymap()
        }
        return JsonResponse(response)


class BaseStoryMapGPView(ViewSet):
    serializer = GStoryMapGPSerializer

    def get_font_css(self):
        pass

    def get_storymap(self):
        pass

    def get_serializer(self, data):
        return self.serializer(data)

    def list(self, request, format=None):
        self.request = request
        response = {
            "font_css": self.get_font_css(),
            "storymap": self.get_storymap()
        }

        return JsonResponse(response)
