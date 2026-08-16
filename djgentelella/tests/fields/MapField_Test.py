from django.core.exceptions import ValidationError
from django.test import TestCase

from djgentelella.fields.maps import (
    DEFAULT_MAX_LENGTH,
    GTPointField,
    GTPointFormField,
    parse_point,
    validate_latlng,
)
from djgentelella.serializers.maps import GTMapSerializer
from djgentelella.views.maps import BaseMapView
from djgentelella.widgets.maps import MapPointInput


class ParsePointTest(TestCase):
    def test_valid(self):
        self.assertEqual(parse_point("9.9327,-84.0875"), (9.9327, -84.0875))

    def test_whitespace_is_tolerated(self):
        self.assertEqual(parse_point(" 9.9327 , -84.0875 "), (9.9327, -84.0875))

    def test_empty(self):
        self.assertIsNone(parse_point(""))
        self.assertIsNone(parse_point(None))

    def test_rejects_bad_values(self):
        for value in ["9.9327", "a,b", "91,0", "-91,0", "0,181", "0,-181",
                      "9.9,-84.1,5", "nan,0"]:
            with self.subTest(value=value):
                self.assertIsNone(parse_point(value), value)


class ValidateLatLngTest(TestCase):
    def assertCode(self, value, code):
        with self.assertRaises(ValidationError) as ctx:
            validate_latlng(value)
        self.assertEqual(ctx.exception.code, code)

    def test_blank_is_allowed(self):
        """Emptiness is `required`'s business, not the validator's."""
        validate_latlng("")
        validate_latlng(None)

    def test_valid(self):
        validate_latlng("9.9327,-84.0875")

    def test_each_failure_has_its_own_message(self):
        self.assertCode("9.9327", "invalid_format")
        self.assertCode("9.9,-84.1,5", "invalid_format")
        self.assertCode("a,b", "invalid_number")
        self.assertCode("91,0", "invalid_latitude")
        self.assertCode("0,181", "invalid_longitude")


class GTPointFormFieldTest(TestCase):
    def test_normalizes_spacing(self):
        field = GTPointFormField()
        self.assertEqual(field.clean(" 9.9327 , -84.0875 "), "9.9327,-84.0875")

    def test_rejects_out_of_range(self):
        with self.assertRaises(ValidationError):
            GTPointFormField().clean("91,0")

    def test_uses_the_map_widget(self):
        self.assertIsInstance(GTPointFormField().widget, MapPointInput)


class GTPointFieldTest(TestCase):
    def test_deconstruct_round_trips(self):
        """
        The bug django-location-field has: without deconstruct() the extra
        kwargs are lost and makemigrations produces an unusable field.
        """
        original = GTPointField(
            zoom=8, center=(9.9327, -84.0875), search=True,
            based_fields=["#id_country"],
        )
        name, path, args, kwargs = original.deconstruct()
        rebuilt = GTPointField(*args, **kwargs)

        self.assertEqual(rebuilt.zoom, 8)
        self.assertEqual(rebuilt.center, (9.9327, -84.0875))
        self.assertEqual(rebuilt.search, True)
        self.assertEqual(rebuilt.based_fields, ["#id_country"])
        self.assertEqual(rebuilt.max_length, DEFAULT_MAX_LENGTH)

    def test_deconstruct_omits_defaults(self):
        _, _, _, kwargs = GTPointField().deconstruct()
        self.assertNotIn("max_length", kwargs)
        self.assertNotIn("zoom", kwargs)
        self.assertNotIn("center", kwargs)
        self.assertNotIn("search", kwargs)

    def test_deconstruct_keeps_a_custom_max_length(self):
        _, _, _, kwargs = GTPointField(max_length=120).deconstruct()
        self.assertEqual(kwargs["max_length"], 120)

    def test_formfield_forwards_the_map_options(self):
        formfield = GTPointField(zoom=8, center=(9.9327, -84.0875)).formfield()
        self.assertIsInstance(formfield, GTPointFormField)
        self.assertIsInstance(formfield.widget, MapPointInput)
        self.assertEqual(formfield.widget.attrs["data-zoom"], 8)
        self.assertEqual(formfield.widget.attrs["data-center"], "9.9327,-84.0875")

    def test_model_validators_reject_bad_points(self):
        field = GTPointField()
        with self.assertRaises(ValidationError):
            field.run_validators("91,0")


class ExampleMapView(BaseMapView):
    def get_center(self):
        return [9.93, -84.09]

    def get_zoom(self):
        return 8

    def get_layers(self):
        return [
            {
                "name": "Offices",
                "color": "#2c7fb8",
                "points": [
                    {"lat": 9.93, "lng": -84.09, "title": "HQ",
                     "popup": "<b>HQ</b>", "weight": 2.0},
                ],
            }
        ]

    def get_heatmap(self):
        return {"name": "Density", "visible": False, "radius": 30}


class BaseMapViewTest(TestCase):
    def test_get_layers_must_be_implemented(self):
        with self.assertRaises(NotImplementedError):
            BaseMapView().get_layers()

    def test_payload_matches_the_serializer(self):
        view = ExampleMapView()
        payload = {
            "fit_bounds": view.get_fit_bounds(),
            "cluster": view.get_cluster(),
            "layers": view.get_layers(),
            "center": view.get_center(),
            "zoom": view.get_zoom(),
            "heatmap": view.get_heatmap(),
        }
        data = GTMapSerializer(payload).data
        self.assertEqual(data["center"], [9.93, -84.09])
        self.assertEqual(data["zoom"], 8)
        self.assertEqual(len(data["layers"]), 1)
        self.assertEqual(data["layers"][0]["name"], "Offices")
        self.assertEqual(data["layers"][0]["points"][0]["lat"], 9.93)
        self.assertEqual(data["heatmap"]["name"], "Density")

    def test_lat_lng_keep_their_precision(self):
        """
        FloatField, not the DecimalField(max_digits=8, decimal_places=4) used by
        the storymap serializer -- 4 decimals is ~11 m of error.
        """
        payload = {
            "fit_bounds": True,
            "cluster": False,
            "layers": [{"name": "x", "points": [
                {"lat": 9.9327123, "lng": -84.0875456}]}],
        }
        data = GTMapSerializer(payload).data
        self.assertEqual(data["layers"][0]["points"][0]["lat"], 9.9327123)
        self.assertEqual(data["layers"][0]["points"][0]["lng"], -84.0875456)
