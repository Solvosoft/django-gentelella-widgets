from djgentelella.fields.maps import parse_point
from djgentelella.groute import register_lookups
from djgentelella.views.maps import BaseMapView

from demoapp.models import Place


@register_lookups(prefix="places", basename="placesmap")
class PlacesMapView(BaseMapView):
    """Every Place on a map, one switchable layer per country.

    Shows the whole contract: filters read from query_params, per-layer
    clustering, popups with HTML and a heatmap derived from the same points.
    """

    colors = ["#2c7fb8", "#d95f0e", "#31a354", "#756bb1", "#c51b8a"]

    def get_places(self):
        queryset = Place.objects.exclude(location="")
        country = self.request.query_params.get("country")
        if country:
            queryset = queryset.filter(country=country)
        return queryset

    def get_cluster(self):
        return True

    def get_layers(self):
        by_country = {}
        for place in self.get_places():
            point = parse_point(place.location)
            if point is None:
                continue
            lat, lng = point
            by_country.setdefault(place.country or "Unknown", []).append(
                {
                    "lat": lat,
                    "lng": lng,
                    "title": place.name,
                    "popup": "<b>%s</b><br>%s" % (place.name, place.city),
                    "weight": 1,
                }
            )
        return [
            {
                "name": country,
                "color": self.colors[index % len(self.colors)],
                "points": points,
            }
            for index, (country, points) in enumerate(sorted(by_country.items()))
        ]

    def get_heatmap(self):
        return {"name": "Density", "visible": False, "radius": 30, "blur": 20}
