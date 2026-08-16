from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from djgentelella.serializers.maps import GTMapSerializer


class BaseMapView(ViewSet):
    """Serves the point payload a ``DJMap`` widget draws.

    Subclass it in ``<app>/gtmaps.py``, override the hooks and register it::

        @register_lookups(prefix="places", basename="placesmap")
        class PlacesMap(BaseMapView):
            def get_layers(self):
                return [{"name": "Offices", "points": [
                    {"lat": 9.93, "lng": -84.09, "popup": "<b>HQ</b>"},
                ]}]

    Then point the widget at ``reverse_lazy('placesmap-list')``.

    Filters sent by the widget arrive in ``self.request.query_params``; narrow
    the queryset inside the hooks, the same contract the chart getters use.
    """

    serializer = GTMapSerializer

    def get_center(self):
        """``[lat, lng]``, or None to fit the map to the points instead."""
        return None

    def get_zoom(self):
        return None

    def get_fit_bounds(self):
        return True

    def get_cluster(self):
        """Default clustering for layers that do not state their own."""
        return False

    def get_layers(self):
        raise NotImplementedError("BaseMapView subclasses must define get_layers")

    def get_heatmap(self):
        return None

    def get_serializer(self, data):
        return self.serializer(data)

    def list(self, request, format=None):
        # Set first, so the hooks below can read query_params.
        self.request = request
        response = {
            "fit_bounds": self.get_fit_bounds(),
            "cluster": self.get_cluster(),
            "layers": self.get_layers(),
        }
        center = self.get_center()
        if center is not None:
            response["center"] = center
        zoom = self.get_zoom()
        if zoom is not None:
            response["zoom"] = zoom
        heatmap = self.get_heatmap()
        if heatmap is not None:
            response["heatmap"] = heatmap
        return Response(self.get_serializer(response).data)
