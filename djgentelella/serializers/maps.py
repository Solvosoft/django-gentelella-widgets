from rest_framework import serializers


class MapPointSerializer(serializers.Serializer):
    """A single marker.

    lat/lng are FloatFields on purpose. The DecimalField(max_digits=8,
    decimal_places=4) used by serializers/storymap.py is not usable here: 4
    decimals is ~11 m of error and max_digits=8 caps the integer part at 4
    digits. JSON has no decimal type either, so a float is what reaches the
    browser regardless.
    """

    lat = serializers.FloatField()
    lng = serializers.FloatField()
    title = serializers.CharField(required=False)
    #: Rendered as-is inside the Leaflet popup, so it may contain HTML.
    popup = serializers.CharField(required=False)
    color = serializers.CharField(required=False)
    icon = serializers.CharField(required=False)
    url = serializers.CharField(required=False)
    weight = serializers.FloatField(required=False)
    extra = serializers.DictField(required=False)


class MapLayerSerializer(serializers.Serializer):
    """A switchable group of markers -- what L.control.layers calls an overlay."""

    name = serializers.CharField(required=False, allow_blank=True)
    visible = serializers.BooleanField(required=False, default=True)
    cluster = serializers.BooleanField(required=False)
    color = serializers.CharField(required=False)
    icon = serializers.CharField(required=False)
    points = MapPointSerializer(many=True)


class HeatmapSerializer(serializers.Serializer):
    """Density overlay. Without points it is derived from the layers' weights."""

    name = serializers.CharField(required=False)
    visible = serializers.BooleanField(required=False, default=True)
    radius = serializers.IntegerField(required=False)
    blur = serializers.IntegerField(required=False)
    max = serializers.FloatField(required=False)
    points = serializers.ListField(
        child=serializers.ListField(child=serializers.FloatField()), required=False
    )


class GTMapSerializer(serializers.Serializer):
    center = serializers.ListField(child=serializers.FloatField(), required=False)
    zoom = serializers.IntegerField(required=False)
    fit_bounds = serializers.BooleanField(required=False, default=True)
    cluster = serializers.BooleanField(required=False, default=False)
    layers = MapLayerSerializer(many=True)
    heatmap = HeatmapSerializer(required=False, allow_null=True)
