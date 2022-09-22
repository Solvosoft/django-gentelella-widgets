from rest_framework.response import Response
from rest_framework.viewsets import ViewSet
from djgentelella.serializers.timeline import GTimelineBase


class BaseTimelineView(ViewSet):
    serializer = GTimelineBase

    def get_title(self):
        pass

    def get_events(self):
        return []

    def get_scale(self):
        return 'human'

    def get_eras(self):
        return []

    def get_serializer(self, data):
        return self.serializer(data)

    def list(self, request, format=None):
        self.request = request
        response = {
            'title': self.get_title(),
            'events': self.get_events(),
            'scale': self.get_scale(),
            'eras': self.get_eras()
        }
        return Response(self.get_serializer(response).data)
