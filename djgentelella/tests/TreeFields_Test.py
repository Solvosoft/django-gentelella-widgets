from pathlib import Path

from django import forms
from django.test import TestCase

import djgentelella
from djgentelella.fields.tree import GentelellaTreeNodeChoiceField, \
    GentelellaTreeNodeMultipleChoiceField
from djgentelella.models import MenuItem
from djgentelella.widgets import trees


class TreeNodeFieldsTestCase(TestCase):
    """The tree fields read tree_depth from django-tree-queries."""

    def setUp(self):
        # a five level chain, so the depths go past the four the CSS used to
        # stop indenting at
        self.nodes = []
        parent = None
        for depth, title in enumerate(
                ['Root', 'Child', 'Grandchild', 'Great', 'GreatGreat']):
            parent = MenuItem.objects.create(
                title=title, url_name=title.lower(), position=depth,
                parent=parent)
            self.nodes.append(parent)
        self.root, self.child, self.grandchild = self.nodes[:3]

    def levels(self, field):
        return {label['text']: label['level']
                for value, label in field.choices if value != ''}

    def test_label_carries_the_tree_depth(self):
        field = GentelellaTreeNodeChoiceField(queryset=MenuItem.objects.all())
        self.assertEqual(self.levels(field),
                         {'Root': 0, 'Child': 1, 'Grandchild': 2,
                          'Great': 3, 'GreatGreat': 4})

    def test_plain_queryset_gets_tree_fields_added(self):
        # the caller passes a queryset that never saw with_tree_fields()
        field = GentelellaTreeNodeChoiceField(queryset=MenuItem.objects.all())
        self.assertEqual(type(field.queryset.query).__name__, 'TreeQuery')

    def test_a_queryset_replaced_after_init_keeps_its_depths(self):
        # scoping a field inside a form's __init__ is the ordinary way to do it,
        # and it goes through the setter rather than through __init__
        class TreeForm(forms.Form):
            item = GentelellaTreeNodeChoiceField(
                queryset=MenuItem.objects.none())

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fields['item'].queryset = MenuItem.objects.all()

        field = TreeForm().fields['item']
        self.assertEqual(type(field.queryset.query).__name__, 'TreeQuery')
        self.assertEqual(self.levels(field),
                         {'Root': 0, 'Child': 1, 'Grandchild': 2,
                          'Great': 3, 'GreatGreat': 4})

    def test_a_replaced_queryset_reaches_the_widget(self):
        field = GentelellaTreeNodeChoiceField(queryset=MenuItem.objects.none())
        field.queryset = MenuItem.objects.filter(title='Child')
        self.assertEqual(self.levels(field), {'Child': 1})
        self.assertEqual(self.levels(field.widget), {'Child': 1})

    def test_disable_uses_the_value_not_the_mere_presence(self):
        field = GentelellaTreeNodeChoiceField(
            queryset=MenuItem.objects.all(), disable0=True, disable1=False)
        disabled = {label['text']: label['disable']
                    for value, label in field.choices if value != ''}
        self.assertTrue(disabled['Root'])
        self.assertFalse(disabled['Child'])
        self.assertFalse(disabled['Grandchild'])

    def test_disable_accepts_levels_beyond_the_first_four(self):
        field = GentelellaTreeNodeChoiceField(
            queryset=MenuItem.objects.all(), disable7=True)
        self.assertEqual(field.disables, {7})

    def test_empty_label_is_renderable_by_the_option_template(self):
        field = GentelellaTreeNodeChoiceField(queryset=MenuItem.objects.all())
        empty = dict(field.choices)['']
        self.assertEqual(empty['text'], '---------')
        self.assertFalse(empty['disable'])

    def test_default_widgets(self):
        single = GentelellaTreeNodeChoiceField(queryset=MenuItem.objects.all())
        multiple = GentelellaTreeNodeMultipleChoiceField(
            queryset=MenuItem.objects.all())
        self.assertIsInstance(single.widget, trees.TreeSelect)
        self.assertIsInstance(multiple.widget, trees.TreeSelectMultiple)

    def test_renders_indent_class_and_disabled_option(self):
        class TreeForm(forms.Form):
            item = GentelellaTreeNodeChoiceField(
                queryset=MenuItem.objects.all(), disable0=True)

        html = str(TreeForm()['item'])
        for level in range(5):
            self.assertIn('class="l%d"' % level, html)
        self.assertIn('disabled', html)
        self.assertIn('Grandchild', html)

    def test_every_rendered_level_has_an_indentation_rule(self):
        # the option classes are useless unless the theme defines them
        css = (Path(djgentelella.__file__).parent / 'static' / 'gentelella' /
               'css' / 'custom.css').read_text()
        for level in range(5):
            self.assertIn('.l%d {' % level, css)

    def test_multiple_field_validates_selection(self):
        field = GentelellaTreeNodeMultipleChoiceField(
            queryset=MenuItem.objects.all())
        selected = field.clean([str(self.child.pk), str(self.grandchild.pk)])
        self.assertCountEqual(selected, [self.child, self.grandchild])
