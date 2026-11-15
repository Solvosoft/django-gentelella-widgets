import os

from django import forms
from django.db import models
from django.test import SimpleTestCase, TestCase

from demoapp.models import ObjectManagerDemoModel, Place, UUIDThing
from djgentelella.fields.tree import GentelellaTreeNodeChoiceField
from djgentelella.forms.forms import GTForm
from djgentelella.forms.widgetmap import FIELD_KINDS, WIDGETS, WIDGETS_BY_KIND, \
    default_widget, field_kind, gt_formfield_callback, usable_widgets, widget_class
from djgentelella.models import MenuItem
from djgentelella.widgets import core as genwidgets
from djgentelella.widgets import maps, trees


def model_field(model, name):
    return model._meta.get_field(name)


class WidgetTableTests(SimpleTestCase):
    def test_every_widget_imports(self):
        for key in WIDGETS:
            self.assertEqual(widget_class(key).__name__, key)

    def test_every_offered_widget_is_known(self):
        for kind, keys in WIDGETS_BY_KIND.items():
            for key in keys:
                self.assertIn(key, WIDGETS, kind)

    def test_kinds(self):
        self.assertEqual(field_kind(model_field(ObjectManagerDemoModel,
                                                'radio_elements')), 'choices')
        self.assertEqual(field_kind(model_field(ObjectManagerDemoModel,
                                                'born_date')), 'date')
        self.assertEqual(field_kind(model_field(Place, 'location')), 'point')
        self.assertEqual(field_kind(model_field(UUIDThing, 'id')), 'uuid')
        self.assertEqual(field_kind(model_field(MenuItem, 'permission')), 'm2m')

    def test_subclasses_are_listed_before_their_bases(self):
        for index, (field_class, _kind) in enumerate(FIELD_KINDS):
            for base, _ in FIELD_KINDS[:index]:
                self.assertFalse(issubclass(field_class, base) and
                                 field_class is not base,
                                 '%s comes after %s' % (field_class, base))

    def test_autocompletes_need_a_lookup_and_trees_a_tree(self):
        self.assertEqual(usable_widgets('fk', can_autocomplete=False),
                         ['Select'])
        self.assertEqual(usable_widgets('fk', is_tree=True),
                         ['AutocompleteSelect', 'Select', 'TreeSelect'])

    def test_defaults(self):
        self.assertEqual(default_widget(model_field(MenuItem, 'parent')),
                         'TreeSelect')
        self.assertEqual(default_widget(model_field(MenuItem, 'permission')),
                         'SelectMultiple')
        self.assertEqual(default_widget(model_field(ObjectManagerDemoModel,
                                                    'field_select')), 'Select')
        self.assertEqual(default_widget(model_field(ObjectManagerDemoModel,
                                                    'description')), 'Textarea')

    def test_a_nullable_boolean_keeps_unknown(self):
        field = gt_formfield_callback(models.BooleanField(null=True))
        self.assertIsInstance(field, forms.NullBooleanField)
        self.assertIs(type(field.widget), genwidgets.NullBooleanSelect)
        self.assertIsNone(field.clean(field.widget.value_from_datadict(
            {'x': 'unknown'}, {}, 'x')))

    def test_a_file_path_is_a_select(self):
        field = gt_formfield_callback(models.FilePathField(
            path=os.path.dirname(__file__), match=r'.*\.py$'))
        self.assertIs(type(field.widget), genwidgets.Select)
        self.assertIn('__init__.py', [label for _value, label in field.choices])


class DemoForm(GTForm, forms.ModelForm):
    class Meta:
        model = ObjectManagerDemoModel
        fields = ['name', 'born_date', 'last_time', 'description', 'radio_elements',
                  'yes_no', 'simple_archive', 'field_select']
        widgets = {'description': genwidgets.TextInput}
        formfield_callback = gt_formfield_callback


class MenuForm(GTForm, forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = ['title', 'parent', 'position']
        formfield_callback = gt_formfield_callback


class PlaceForm(GTForm, forms.ModelForm):
    class Meta:
        model = Place
        fields = ['name', 'location']
        formfield_callback = gt_formfield_callback


class CallbackTests(TestCase):
    def widget(self, form, name):
        return type(form.fields[name].widget)

    def test_a_model_form(self):
        form = DemoForm()
        self.assertIs(self.widget(form, 'name'), genwidgets.TextInput)
        self.assertIs(self.widget(form, 'born_date'), genwidgets.DateInput)
        self.assertIs(self.widget(form, 'last_time'), genwidgets.DateTimeInput)
        self.assertIs(self.widget(form, 'radio_elements'), genwidgets.Select)
        self.assertIs(self.widget(form, 'yes_no'), genwidgets.YesNoInput)
        self.assertIs(self.widget(form, 'simple_archive'),
                      genwidgets.ClearableFileInput)
        self.assertIs(self.widget(form, 'field_select'), genwidgets.Select)
        # Meta.widgets wins.
        self.assertIs(self.widget(form, 'description'), genwidgets.TextInput)
        self.assertIn('<select', str(form['radio_elements']))

    def test_a_tree_gets_the_tree_field(self):
        root = MenuItem.objects.create(title='Root', url_name='root')
        MenuItem.objects.create(title='Leaf', url_name='leaf', parent=root)
        form = MenuForm()
        self.assertIs(self.widget(form, 'parent'), trees.TreeSelect)
        self.assertIsInstance(form.fields['parent'], GentelellaTreeNodeChoiceField)
        html = str(form['parent'])
        self.assertIn('>Root</option>', html)
        self.assertIn('class="l1"', html)

    def test_a_point(self):
        self.assertIs(self.widget(PlaceForm(), 'location'), maps.MapPointInput)

    def test_saving(self):
        form = MenuForm({'title': 'Home', 'position': 1})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.save().parent)
        callback_field = gt_formfield_callback(model_field(MenuItem, 'id'))
        self.assertIsNone(callback_field)
