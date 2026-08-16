from django import forms
from django.forms import formset_factory
from django.template import Context, Template
from django.test import TestCase

from djgentelella.widgets.maps import MapPointInput


class FormClass(forms.Form):
    location = forms.CharField(widget=MapPointInput())


class ConfiguredFormClass(forms.Form):
    location = forms.CharField(
        widget=MapPointInput(
            zoom=8,
            center=(9.9327, -84.0875),
            height="400px",
            search=True,
            based_fields=["#id_country", "#id_city"],
        )
    )


class RequiredFormClass(forms.Form):
    mandatory = forms.CharField(widget=MapPointInput(), required=True)
    optional = forms.CharField(widget=MapPointInput(), required=False)
    frozen = forms.CharField(widget=MapPointInput(), disabled=True)


class MapPointWidgetUnitTest(TestCase):
    def render(self, msg, context={}):
        return Template(msg).render(Context(context))

    def setUp(self):
        self.basicform = FormClass()
        self.prefixform = FormClass(prefix="newname")
        self.configuredform = ConfiguredFormClass()

    def test_check_names(self):
        """
        This test check how to deal with names and ids in the widget.
        reason: Names could be modify in templates accidentally.
        """
        noprefix = self.render("{{form}}", {"form": self.basicform})
        withprefix = self.render("{{form}}", {"form": self.prefixform})

        self.assertIn('id="id_location"', noprefix)
        self.assertIn('name="location"', noprefix)
        self.assertIn('id="id_newname-location"', withprefix)
        self.assertIn('name="newname-location"', withprefix)

    def test_data_widget_is_stamped(self):
        """
        data-widget is what gt_find_initialize dispatches on and what the
        selenium helper asserts against, so it is the widget's real contract.
        """
        rendered = self.render("{{form}}", {"form": self.basicform})
        self.assertIn('data-widget="MapPointInput"', rendered)

    def test_sibling_ids_follow_the_input_id(self):
        """
        The JS looks its DOM up as id + '_map' / '_locate' / '_clear'.
        """
        rendered = self.render("{{form}}", {"form": self.prefixform})
        for suffix in ["_container", "_map", "_locate", "_clear", "_status"]:
            self.assertIn('id="id_newname-location%s"' % suffix, rendered)

    def test_named_kwargs_become_data_attrs(self):
        rendered = self.render("{{form}}", {"form": self.configuredform})
        self.assertIn('data-zoom="8"', rendered)
        self.assertIn('data-center="9.9327,-84.0875"', rendered)
        self.assertIn("data-based-fields=", rendered)
        self.assertIn("#id_country", rendered)
        self.assertIn('id="id_location_search"', rendered)
        self.assertIn("height: 400px", rendered)

    def test_search_box_is_opt_in(self):
        """
        Nominatim's usage policy caps callers at 1 req/s, so the search box must
        not appear unless the developer asked for it.
        """
        rendered = self.render("{{form}}", {"form": self.basicform})
        self.assertNotIn('id="id_location_search"', rendered)

    def test_required_and_disabled_are_kept(self):
        """
        Deliberate inversion of the timeline/storymap behaviour: those are
        read-only viewers that strip both, but this widget submits a value and
        needs browser validation to work.
        """
        rendered = self.render("{{form}}", {"form": RequiredFormClass()})
        self.assertIn('name="mandatory"', rendered)
        self.assertIn("required", rendered)
        self.assertIn("disabled", rendered)

    def test_value_is_rendered_back(self):
        form = FormClass(data={"location": "9.932700,-84.087500"})
        form.is_valid()
        rendered = self.render("{{form}}", {"form": form})
        self.assertIn('value="9.932700,-84.087500"', rendered)

    def test_formset_ids(self):
        formset = formset_factory(FormClass, extra=2)()
        rendered = self.render("{{formset}}", {"formset": formset})
        self.assertIn('id="id_form-0-location"', rendered)
        self.assertIn('id="id_form-1-location"', rendered)
        self.assertIn('id="id_form-0-location_map"', rendered)
        self.assertIn('id="id_form-1-location_map"', rendered)

    def test_no_media_is_declared(self):
        """
        This project ships all JS through base.js + widgets.js; no widget in it
        declares Media, and adding one here would emit duplicate script tags.
        """
        self.assertEqual(str(FormClass().media), "")
