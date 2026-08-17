"""Browser tests for the Leaflet widgets.

Covers /maps/ (MapPointInput, the GPS point form field) and /maps/dashboard
(DJMap, points from an API), plus two regressions that are invisible to the
Python tests and total when they happen -- see LeafletBootstrapTest.
"""

from django.test import tag

from demoapp.models import Place

from .base import By, SeleniumTestCase

PLACES = [
    ('Sede Central', 'Costa Rica', 'San Jose', '9.932700,-84.087500'),
    ('Sucursal Heredia', 'Costa Rica', 'Heredia', '9.998200,-84.116500'),
    ('Sucursal Cartago', 'Costa Rica', 'Cartago', '9.864700,-83.919400'),
    ('Oficina Panama', 'Panama', 'Panama City', '8.983300,-79.516700'),
]

LATLNG_RE = r'^-?\d+\.\d{6},-?\d+\.\d{6}$'

#: Ciudad de Guatemala. Deliberately nowhere near the form's default centre
#: (San Jose, Costa Rica), so a point that lands on the default instead of
#: where it was asked for cannot pass unnoticed.
GUATEMALA_CITY = (14.6349, -90.5069)


class MapsTestBase(SeleniumTestCase):
    def setup_data(self):
        for name, country, city, location in PLACES:
            Place.objects.create(
                name=name, country=country, city=city, location=location)


@tag('selenium')
class LeafletBootstrapTest(MapsTestBase):
    """/maps/ -- the two integration hazards this library has with Leaflet."""

    def test_leaflet_is_version_1(self):
        """storymapjs embeds Leaflet 0.7.7 and assigns it to window.L.

        Both bundles are on this page. If the maps bundle were emitted before
        the readonly one, window.L would be silently downgraded and every map
        would fail against a 0.7 API.
        """
        self.go('/maps/')
        self.assertEqual(self.js('return L.version.charAt(0)'), '1')

    def test_marker_icon_path_is_explicit(self):
        """pylp's urlreplace base64-inlines the CSS Leaflet uses to guess its
        image path, so the guess must never be relied on."""
        self.go('/maps/')
        icon_url = self.js(
            "return L.Icon.Default.prototype.options.iconUrl || ''")
        self.assertIn('marker-icon.png', icon_url)
        self.assertNotIn('data:', icon_url)

    def test_storymap_still_boots(self):
        """The load-order fix must not break the widget that caused it."""
        self.go('/mapbased_view')
        self.assertEqual(
            self.assert_widget_ready('[data-widget="MapBasedStoryMapInput"]'),
            'MapBasedStoryMapInput')


@tag('selenium')
class MapPointInputTest(MapsTestBase):
    """/maps/ -- picking a GPS point."""

    def open_form(self):
        self.go('/maps/')
        self.assertEqual(
            self.assert_widget_ready('#id_location'), 'MapPointInput')
        self.wait_js(
            "return !!window._gt_map_point_widgets['id_location']")

    def test_widget_initialises(self):
        self.open_form()
        self.assertTrue(self.js(
            "return !!document.querySelector('#id_location_map .leaflet-pane')"))

    def test_click_on_the_map_fills_the_input_and_fires_change(self):
        """The value contract, plus the change event django-location-field
        never dispatches -- without it Parsley and autosave miss the update."""
        self.open_form()
        self.js("window.__changes = 0;"
                "document.getElementById('id_location')"
                "  .addEventListener('change', () => window.__changes++);")
        self.driver.find_element(By.CSS_SELECTOR, '#id_location_map').click()
        self.wait_js("return document.getElementById('id_location').value !== ''")

        self.assertRegex(
            self.js("return document.getElementById('id_location').value"),
            LATLNG_RE)
        self.assertGreaterEqual(self.js('return window.__changes'), 1)

    def set_location(self, value):
        """Set the input the way a user typing does.

        Deliberately not jQuery's .trigger('input'): an unrelated plugin
        already on every djgentelella page throws on that event (reproducible
        on /inputmask/ with no map involved), which would make these tests fail
        for a reason that has nothing to do with the widget.
        """
        self.js(
            "const e = document.getElementById('id_location');"
            "e.value = arguments[0];"
            "e.dispatchEvent(new Event('input', {bubbles: true}));", value)

    def test_marker_follows_a_typed_value(self):
        self.open_form()
        self.set_location('9.932700,-84.087500')
        self.wait_js(
            "return !!window._gt_map_point_widgets['id_location']"
            ".engine.getPoint()")
        point = self.js(
            "const p = window._gt_map_point_widgets['id_location']"
            "  .engine.getPoint(); return [p.lat, p.lng];")
        self.assertAlmostEqual(point[0], 9.9327, places=3)
        self.assertAlmostEqual(point[1], -84.0875, places=3)

    def test_garbage_is_reported_not_swallowed(self):
        self.open_form()
        self.set_location('not a point')
        self.wait_js(
            "return document.getElementById('id_location')"
            ".classList.contains('is-invalid')")
        self.assertTrue(self.js(
            "return document.getElementById('id_location_status')"
            ".textContent.length > 0"))

    def test_clear_button_empties_everything(self):
        self.open_form()
        self.set_location('9.932700,-84.087500')
        self.wait_js("return !!window._gt_map_point_widgets['id_location']"
                     ".engine.getPoint()")
        self.driver.find_element(By.CSS_SELECTOR, '#id_location_clear').click()
        self.wait_js("return document.getElementById('id_location').value === ''")
        self.assertIsNone(self.js(
            "return window._gt_map_point_widgets['id_location']"
            ".engine.getPoint()"))

    def submit_and_wait_for(self, name):
        """Submit the form and return the Place once it is really in the table.

        Not `wait_js("readyState === 'complete'")`: the click only *starts* the
        navigation, and the document it asks about is the one still on screen,
        which has been complete all along. That wait returns immediately, so
        the assertion races the POST -- it wins on an idle machine and loses
        under the full suite, which is exactly the kind of flake that gets a
        real failure dismissed. Waiting for the row is the thing actually being
        waited for.
        """
        self.driver.find_element(
            By.CSS_SELECTOR, 'form button[type=submit]').click()
        self.wait.until(
            lambda driver: Place.objects.filter(name=name).exists(),
            'the form submit never reached the database')
        return Place.objects.get(name=name)

    def test_point_round_trips_through_a_form_submit(self):
        """The only assertion that proves the whole contract end to end."""
        self.open_form()
        self.js("document.getElementById('id_name').value = 'Nueva sede';")
        self.set_location('9.932700,-84.087500')

        place = self.submit_and_wait_for('Nueva sede')
        self.assertEqual(place.location, '9.932700,-84.087500')

    def test_a_point_picked_on_the_map_lands_where_it_was_clicked(self):
        """Fill the whole form, placing the point by clicking the map.

        The other click test only checks the value *looks* like a point. This
        one pans the map over Guatemala City and clicks dead centre, so the
        assertion is on the coordinates themselves.

        What that catches is the click resolving against the wrong view --
        landing on the widget's configured centre, or on a stale one, instead
        of where the map is actually looking. Verified by removing the pan:
        the point comes back as 9.932717,-84.087514, the Costa Rica default,
        and the test fails by 4.7 degrees. Note it would not catch a *uniform*
        projection error, since the same constant drives the pan and the
        expectation; what it pins is that the two agree.

        A capital far from the default centre on purpose: a wrong-view bug
        that landed a few kilometres off would otherwise pass unnoticed.
        """
        self.open_form()

        # setView, not setPoint: this moves the viewport without placing
        # anything, so the point that ends up stored can only come from the
        # click below.
        self.js(
            "window._gt_map_point_widgets['id_location'].engine.map"
            "  .setView([%s, %s], 15);" % GUATEMALA_CITY)
        self.wait_js(
            "return window._gt_map_point_widgets['id_location'].engine.map"
            "  .getZoom() === 15")

        self.js("document.getElementById('id_name').value = 'Sede Guatemala';"
                "document.getElementById('id_country').value = 'Guatemala';"
                "document.getElementById('id_city').value = "
                "  'Ciudad de Guatemala';")
        self.driver.find_element(By.CSS_SELECTOR, '#id_location_map').click()
        self.wait_js("return document.getElementById('id_location').value !== ''")

        value = self.js("return document.getElementById('id_location').value")
        self.assertRegex(value, LATLNG_RE)
        lat, lng = (float(part) for part in value.split(','))
        # One tenth of a degree is ~11 km: wide enough for the click landing a
        # few pixels off centre, far tighter than the distance to any other
        # capital.
        self.assertAlmostEqual(lat, GUATEMALA_CITY[0], delta=0.1)
        self.assertAlmostEqual(lng, GUATEMALA_CITY[1], delta=0.1)

        place = self.submit_and_wait_for('Sede Guatemala')
        self.assertEqual(place.city, 'Ciudad de Guatemala')
        # Saved verbatim: the widget owns the formatting, the field stores the
        # string it produced.
        self.assertEqual(place.location, value)


@tag('selenium')
class DJMapTest(MapsTestBase):
    """/maps/dashboard -- many points from an API."""

    def open_dashboard(self):
        self.go('/maps/dashboard')
        self.assertEqual(
            self.assert_widget_ready('[data-widget="DJMap"]'), 'DJMap')
        self.wait_js(
            "return !!jQuery('.gentelella_map').data('mapInstance')")

    def marker_count(self):
        return self.js(
            "return document.querySelectorAll("
            "  '.leaflet-marker-icon:not(.marker-cluster)').length"
            "+ document.querySelectorAll('.marker-cluster').length;")

    def test_points_are_drawn(self):
        self.open_dashboard()
        self.wait_js("return document.querySelectorAll("
                     "'.leaflet-marker-icon').length > 0")
        self.assertGreater(self.marker_count(), 0)

    def layer_markers(self, layer_name):
        """The markers a layer actually put on the map, with their popups.

        Read off the Leaflet group rather than the DOM: clustering is on for
        this dashboard, so at the default zoom the individual markers are
        collapsed into cluster icons and simply are not in the document. The
        group holds them either way, which is what "the layer drew them" means
        here.
        """
        return self.js(
            "const engine = jQuery('.gentelella_map').data('mapInstance');"
            "const layer = engine.layers[arguments[0]];"
            "if (!layer) return null;"
            "return {"
            "  onMap: engine.map.hasLayer(layer.group),"
            "  markers: layer.group.getLayers().map(function (m) {"
            "    return {lat: m.getLatLng().lat, lng: m.getLatLng().lng,"
            "            popup: m.getPopup() ? m.getPopup().getContent() : ''};"
            "  })"
            "};", layer_name)

    def test_the_costa_rica_layer_draws_every_city_the_api_returned(self):
        """The Costa Rica cities reach the map, with the right coordinates.

        test_points_are_drawn only counts icons, so it passes with one marker
        in the wrong place. This checks the payload survived the whole trip:
        the Places exist only in the database, the page holds no coordinates of
        its own, so anything asserted here got there through
        /gtapis/places/ -- the BaseMapView in demoapp/gtmaps.py -- and then
        through gt_map_render_data into a Leaflet group.
        """
        self.open_dashboard()
        self.wait_js(
            "const e = jQuery('.gentelella_map').data('mapInstance');"
            "return !!(e && e.layers && e.layers['Costa Rica']);")

        layer = self.layer_markers('Costa Rica')
        self.assertIsNotNone(layer, 'the API returned no Costa Rica layer')
        self.assertTrue(layer['onMap'],
                        'the Costa Rica layer was built but never added')

        expected = {city: location for _, country, city, location in PLACES
                    if country == 'Costa Rica'}
        self.assertEqual(len(layer['markers']), len(expected))

        # Keyed by city, taken out of the popup the serializer built, so a
        # mismatch names the city instead of just a coordinate pair.
        drawn = {}
        for marker in layer['markers']:
            city = marker['popup'].split('<br>')[-1]
            drawn[city] = (marker['lat'], marker['lng'])

        self.assertEqual(sorted(drawn), sorted(expected))
        for city, location in expected.items():
            lat, lng = (float(part) for part in location.split(','))
            self.assertAlmostEqual(drawn[city][0], lat, places=4, msg=city)
            self.assertAlmostEqual(drawn[city][1], lng, places=4, msg=city)

        # Panama has its own layer: the split is per country, not one bag of
        # points with a country attribute.
        panama = self.layer_markers('Panama')
        self.assertEqual(len(panama['markers']), 1)
        self.assertNotIn('Panama City', drawn)

    def test_clustering_plugin_is_available(self):
        """use_maps is on in the demo settings, so both plugins must be there."""
        self.open_dashboard()
        self.assertEqual(self.js('return typeof L.markerClusterGroup'),
                         'function')
        self.assertEqual(self.js('return typeof L.heatLayer'), 'function')

    def test_layer_control_lists_every_country_and_the_heatmap(self):
        self.open_dashboard()
        self.wait_js("return !!document.querySelector('.leaflet-control-layers')")
        labels = self.js(
            "return Array.from(document.querySelectorAll("
            "  '.leaflet-control-layers-overlays label'))"
            "  .map(l => l.textContent.trim());")
        self.assertIn('Costa Rica', labels)
        self.assertIn('Panama', labels)
        self.assertIn('Density', labels)

    def test_filter_refetches_through_the_api(self):
        """data-country="#id_country_filter" is resolved by gt_resolve_value,
        the same syntax the chart widget uses."""
        self.open_dashboard()
        self.wait_js("return !!document.querySelector('.leaflet-control-layers')")
        self.js("const e = document.getElementById('id_country_filter');"
                "e.value = 'Panama';"
                "e.dispatchEvent(new Event('change', {bubbles: true}));")
        self.wait_js(
            "return Array.from(document.querySelectorAll("
            "  '.leaflet-control-layers-overlays label'))"
            "  .map(l => l.textContent.trim()).indexOf('Costa Rica') === -1")

        labels = self.js(
            "return Array.from(document.querySelectorAll("
            "  '.leaflet-control-layers-overlays label'))"
            "  .map(l => l.textContent.trim());")
        self.assertIn('Panama', labels)
        self.assertNotIn('Costa Rica', labels)

    def test_reinitialising_does_not_leak_a_map(self):
        """api_list.js and reopened modals re-run gt_find_initialize on the same
        ids; without the engine registry Leaflet throws "Map container is
        already initialized" and the old map keeps fetching tiles."""
        self.open_dashboard()
        before = self.js('return Object.keys(_gt_maps).length;')
        self.js("gt_find_initialize(jQuery('body'));")
        self.wait_js("return !!jQuery('.gentelella_map').data('mapInstance')")

        self.assertEqual(self.js('return Object.keys(_gt_maps).length;'), before)
        errors = [entry['message'] for entry in self.driver.get_log('browser')
                  if 'already initialized' in entry['message']]
        self.assertEqual(errors, [])
