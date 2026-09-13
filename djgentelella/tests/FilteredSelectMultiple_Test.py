from django import forms
from django.forms import formset_factory
from django.template import Context, Template
from django.test import TestCase
from django.urls import reverse_lazy

from djgentelella.widgets.selectmultiple import FilteredSelectMultiple

CHOICES = [
    ('Compiled', [('c', 'C'), ('go', 'Go')]),
    ('Interpreted', [('py', 'Python'), ('rb', 'Ruby')]),
]


class StaticFormClass(forms.Form):
    languages = forms.MultipleChoiceField(
        choices=CHOICES, required=False, widget=FilteredSelectMultiple()
    )


class NamedFormClass(forms.Form):
    languages = forms.MultipleChoiceField(
        choices=CHOICES,
        required=False,
        widget=FilteredSelectMultiple(verbose_name='languages', is_stacked=True),
    )


class ApiFormClass(forms.Form):
    people = forms.MultipleChoiceField(
        choices=[], required=False, widget=FilteredSelectMultiple(url='personbasename')
    )


class FilteredSelectMultipleUnitTest(TestCase):
    def render(self, msg, context={}):
        return Template(msg).render(Context(context))

    def setUp(self):
        self.basicform = StaticFormClass()
        self.prefixform = StaticFormClass(prefix='newname')
        self.namedform = NamedFormClass()

    def test_check_names(self):
        noprefix = self.render('{{form}}', {'form': self.basicform})
        withprefix = self.render('{{form}}', {'form': self.prefixform})
        self.assertIn('id="id_languages"', noprefix)
        self.assertIn('name="languages"', noprefix)
        self.assertIn('id="id_newname-languages"', withprefix)
        self.assertIn('name="newname-languages"', withprefix)

    def test_data_widget_is_stamped(self):
        rendered = self.render('{{form}}', {'form': self.basicform})
        self.assertIn('data-widget="FilteredSelectMultiple"', rendered)

    def test_sibling_ids_follow_the_input_id(self):
        rendered = self.render('{{form}}', {'form': self.prefixform})
        for suffix in [
            '_container',
            '_available',
            '_filter',
            '_add',
            '_remove',
            '_addall',
            '_removeall',
            '_available_count',
            '_chosen_count',
        ]:
            self.assertIn('id="id_newname-languages%s"' % suffix, rendered)

    def test_two_instances_do_not_share_ids(self):
        rendered = self.render(
            '{{one}}{{two}}',
            {'one': self.basicform, 'two': StaticFormClass(prefix='second')},
        )
        self.assertIn('id="id_languages_container"', rendered)
        self.assertIn('id="id_second-languages_container"', rendered)

    def test_select_is_multiple(self):
        rendered = self.render('{{form}}', {'form': self.basicform})
        self.assertIn('multiple', rendered)

    def test_optgroups_are_rendered(self):
        rendered = self.render('{{form}}', {'form': self.basicform})
        self.assertIn('<optgroup label="Compiled">', rendered)
        self.assertIn('<optgroup label="Interpreted">', rendered)
        self.assertIn('value="py"', rendered)

    def test_every_choice_is_rendered_without_an_api(self):
        # No endpoint: the javascript splits the list, so the markup has to
        # carry every option or the available panel comes up empty.
        rendered = self.render('{{form}}', {'form': self.basicform})
        for value in ['c', 'go', 'py', 'rb']:
            self.assertIn('value="%s"' % value, rendered)

    def test_selected_value_stays_selected(self):
        form = StaticFormClass(data={'languages': ['py']})
        rendered = self.render('{{form}}', {'form': form})
        self.assertIn('<option value="py" selected', rendered)

    def test_verbose_name_drives_the_panel_titles(self):
        rendered = self.render('{{form}}', {'form': self.namedform})
        self.assertIn('Available languages', rendered)
        self.assertIn('Chosen languages', rendered)

    def test_verbose_name_falls_back_to_the_field_name(self):
        rendered = self.render('{{form}}', {'form': self.basicform})
        self.assertIn('Available languages', rendered)

    def test_is_stacked_adds_its_class(self):
        self.assertIn(
            'gt-fsm-stacked', self.render('{{form}}', {'form': self.namedform})
        )
        self.assertNotIn(
            'gt-fsm-stacked', self.render('{{form}}', {'form': self.basicform})
        )

    def test_url_is_reversed_into_data_url(self):
        rendered = self.render('{{form}}', {'form': ApiFormClass()})
        self.assertIn(
            'data-url="%s"' % reverse_lazy('personbasename-list'), rendered
        )

    def test_no_data_url_without_an_endpoint(self):
        self.assertNotIn('data-url', self.render('{{form}}', {'form': self.basicform}))

    def test_add_url_renders_the_create_button_and_its_own_modal(self):
        class AddFormClass(forms.Form):
            languages = forms.MultipleChoiceField(
                choices=CHOICES,
                required=False,
                widget=FilteredSelectMultiple(add_url='/create/'),
            )

        rendered = self.render('{{form}}', {'form': AddFormClass()})
        self.assertIn('data-addurl="/create/"', rendered)
        self.assertIn('id="id_languages_modal"', rendered)

    def test_no_create_button_without_add_url(self):
        rendered = self.render('{{form}}', {'form': self.basicform})
        self.assertNotIn('gt-fsm-create', rendered)
        self.assertNotIn('gt-fsm-modal', rendered)

    def test_formset_rows_get_their_own_ids(self):
        FormSet = formset_factory(StaticFormClass, extra=2)
        rendered = self.render('{{formset}}', {'formset': FormSet()})
        self.assertIn('id="id_form-0-languages_container"', rendered)
        self.assertIn('id="id_form-1-languages_container"', rendered)
