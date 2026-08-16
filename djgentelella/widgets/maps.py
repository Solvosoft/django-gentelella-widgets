import json

from django.utils.translation import gettext_lazy as _

from .core import TextInput, update_kwargs


class MapPointInput(TextInput):
    """
    Text input backed by a Leaflet map for picking a single GPS point.

    The value is the plain string ``"lat,lng"`` -- no GeoDjango, GDAL or PostGIS
    involved, so it works on SQLite. The point can be set by clicking the map,
    dragging the marker, typing into the input, the "use my location" button or,
    when enabled, an address search.

    Unlike the read-only viewers in this library (``UrlTimeLineInput``,
    ``MapBasedStoryMapInput``) this widget submits a value, so ``required`` and
    ``disabled`` are deliberately left alone.

    :param zoom: initial zoom level
    :param center: ``"lat,lng"`` or a ``(lat, lng)`` pair used when there is no
                   value yet
    :param height: CSS height for the map container, e.g. ``"400px"``
    :param search: show the address search box. Off by default -- it geocodes
                   through Nominatim, whose usage policy caps callers at 1 req/s
                   and forbids heavy automated use.
    :param locate: show the "use my location" button (hidden by the JS anyway
                   outside a secure context, where the browser refuses to answer)
    :param based_fields: CSS selectors of fields whose values are joined and
                         geocoded to place the marker, e.g.
                         ``['#id_country', '#id_city']``
    :param based_overwrite: let ``based_fields`` move a point the user already
                            placed. Off by default.
    :param tile_url: tile layer template, defaults to OpenStreetMap
    :param geocoder_url: Nominatim compatible endpoint, for self-hosting
    """

    template_name = "gentelella/widgets/map_point.html"

    def __init__(self, attrs=None, extraskwargs=True, zoom=None, center=None,
                 height=None, search=False, locate=True, based_fields=None,
                 based_overwrite=False, tile_url=None, tile_attribution=None,
                 geocoder_url=None):
        if extraskwargs:
            attrs = update_kwargs(attrs, self.__class__.__name__)
        attrs = attrs or {}
        if zoom is not None:
            attrs["data-zoom"] = zoom
        if center is not None:
            attrs["data-center"] = self.format_center(center)
        if height is not None:
            attrs["data-height"] = height
        if based_fields:
            attrs["data-based-fields"] = json.dumps(list(based_fields))
        if based_overwrite:
            attrs["data-based-overwrite"] = "true"
        if tile_url is not None:
            attrs["data-tile-url"] = tile_url
        if tile_attribution is not None:
            attrs["data-tile-attribution"] = tile_attribution
        if geocoder_url is not None:
            attrs["data-geocoder-url"] = geocoder_url
        self.search = search
        self.locate = locate
        super().__init__(attrs, extraskwargs=False)

    @staticmethod
    def format_center(center):
        if isinstance(center, (list, tuple)):
            return "%s,%s" % (center[0], center[1])
        return center

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs=attrs)
        # Django templates cannot read widget.attrs.data-search (the hyphen is
        # parsed as a subtraction), so the flags travel through the context the
        # way CalendarInput passes events/options.
        context["show_search"] = self.search
        context["show_locate"] = self.locate
        context["map_height"] = self.attrs.get("data-height")
        context["search_placeholder"] = _("Search address")
        context["locate_title"] = _("Use my location")
        context["clear_title"] = _("Clear")
        return context
