Map widgets
^^^^^^^^^^^^^^^^^^^^^^^^^

Two Leaflet based widgets sharing one JavaScript engine
(``gentelella/js/base/maplib.js``):

* :class:`~djgentelella.widgets.maps.MapPointInput` -- a form field that asks
  the user for a single GPS point.
* ``DJMap`` -- a dashboard map that draws many points fetched from an API,
  the sibling of the ``DJGraph`` chart widget.

Tiles come from OpenStreetMap and no API key is involved. The point is stored
as the plain string ``"latitude,longitude"``, so **GeoDjango, GDAL and PostGIS
are not needed** and everything works on SQLite.

Loading the static files
""""""""""""""""""""""""""""""""

Leaflet itself is always loaded. Marker clustering and the heatmap are extra
libraries, enabled with the ``use_maps`` define::

    DEFAULT_JS_IMPORTS = {
        'use_maps': True,
    }

Without it the map still works: clustered layers fall back to plain layer
groups and the heatmap is skipped, each with a console warning.

.. note::

   The widgets are initialised from ``gentelella/js/base.js``, which is
   generated and not shipped in the repository. Run
   ``python manage.py createbasejs`` after installing or upgrading, or the
   widgets silently never start.

Asking for a GPS point
""""""""""""""""""""""""""""""""

``MapPointInput`` renders a normal text input plus a map. The point can be set
by clicking the map, dragging the marker, typing the value, pressing the "use
my location" button or searching an address. Every path writes
``"lat,lng"`` into the input and dispatches ``input`` and ``change``, so
validation and autosave see the update.

**Usage**

.. code:: python

    from django import forms
    from djgentelella.forms.forms import GTForm
    from djgentelella.widgets.maps import MapPointInput

    class PlaceForm(GTForm, forms.Form):
        location = forms.CharField(widget=MapPointInput(
            zoom=8, center=(9.9327, -84.0875), search=True))

Or, with validation and a model field included:

.. code:: python

    from django.db import models
    from djgentelella.fields.maps import GTPointField

    class Place(models.Model):
        name = models.CharField(max_length=150)
        country = models.CharField(max_length=100, blank=True)
        city = models.CharField(max_length=100, blank=True)
        location = GTPointField(
            zoom=8,
            center=(9.9327, -84.0875),
            based_fields=['#id_country', '#id_city'],
        )

``GTPointField`` is a ``CharField`` underneath. Use
``djgentelella.fields.maps.parse_point(place.location)`` to get
``(lat, lng)`` floats back, or ``None`` when the value is empty or malformed.

**Widget options**

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Option
     - Default
     - Description
   * - ``zoom``
     - ``13``
     - Initial zoom level.
   * - ``center``
     - ``(0, 0)``
     - Where to look when the field has no value yet.
   * - ``height``
     - ``280px``
     - Map height. Also settable in CSS through ``.gt-map``.
   * - ``search``
     - ``False``
     - Show the address search box.
   * - ``locate``
     - ``True``
     - Show the "use my location" button.
   * - ``based_fields``
     - ``None``
     - CSS selectors whose joined values are geocoded to place the marker.
   * - ``based_overwrite``
     - ``False``
     - Let ``based_fields`` move a point the user already placed.
   * - ``tile_url``
     - OpenStreetMap
     - Tile layer template.
   * - ``tile_attribution``
     - OpenStreetMap
     - Attribution line for ``tile_url``. Most providers require one, so set
       it whenever you set ``tile_url``.
   * - ``geocoder_url``
     - Nominatim
     - Nominatim compatible endpoint.

.. note::

   "Use my location" relies on ``navigator.geolocation``, which browsers only
   answer over **https or on localhost**. Outside a secure context the button
   is not rendered at all.

.. warning::

   Address search and ``based_fields`` geocode through
   `Nominatim <https://operations.osmfoundation.org/policies/nominatim/>`_,
   whose usage policy caps callers at one request per second and forbids heavy
   automated use. That is why ``search`` is off by default. For anything
   beyond a low-traffic site, run your own instance and point ``geocoder_url``
   at it.

Showing points from an API
""""""""""""""""""""""""""""""""

Subclass :class:`~djgentelella.views.maps.BaseMapView` in ``<app>/gtmaps.py``
(auto-imported, like ``gtcharts.py``) and register it:

.. code:: python

    from djgentelella.groute import register_lookups
    from djgentelella.views.maps import BaseMapView

    @register_lookups(prefix="places", basename="placesmap")
    class PlacesMapView(BaseMapView):
        def get_cluster(self):
            return True

        def get_layers(self):
            country = self.request.query_params.get('country')
            queryset = Place.objects.all()
            if country:
                queryset = queryset.filter(country=country)
            return [{
                'name': 'Places',
                'color': '#2c7fb8',
                'points': [
                    {'lat': lat, 'lng': lng, 'title': place.name,
                     'popup': '<b>%s</b>' % place.name}
                    for place in queryset
                ],
            }]

Then drop the map into a template:

.. code:: django

    {% include 'gentelella/widgets/djmap.html' with map_url=places_url height='480px' %}

**Filters.** Every ``data-*`` attribute other than the reserved ones becomes a
query parameter, using the same syntax as the chart widget: a literal, a
``#selector`` / ``.selector`` read from a live element, or ``{funcName}`` to
call a global function.

.. code:: django

    {% include 'gentelella/widgets/djmap.html' with map_url=places_url dataparams='data-country="#id_country"' %}

Call ``refreshGentelellaMap('.gentelella_map')`` to re-fetch, for instance from
a filter's ``change`` handler. Adding ``data-refetch-on-move="true"`` re-fetches
as the map is panned, sending ``bbox`` and ``zoom``.

**The JSON contract**

.. code:: json

    {
      "center": [9.93, -84.09],
      "zoom": 8,
      "fit_bounds": true,
      "cluster": true,
      "layers": [
        {"name": "Offices", "visible": true, "cluster": true, "color": "#1f77b4",
         "points": [
           {"lat": 9.93, "lng": -84.09, "title": "HQ",
            "popup": "<b>HQ</b><br>San Jose", "color": "#d62728",
            "icon": "fa fa-building", "url": "/place/1/", "weight": 1.0}
         ]}
      ],
      "heatmap": {"name": "Density", "visible": false, "radius": 25, "blur": 15}
    }

Each layer is a switchable overlay in Leaflet's layer control, and the heatmap
sits alongside them. ``points`` may also be given at the top level as a
shorthand for a single unnamed layer. A point with ``color`` or ``icon`` is
drawn as a coloured pin; ``popup`` is inserted as HTML.

.. note::

   ``lat``/``lng`` are serialized as floats, not decimals, so full GPS
   precision survives the round trip.
