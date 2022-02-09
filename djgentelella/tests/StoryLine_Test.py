from django.core.exceptions import ImproperlyConfigured
from django.template import Template, Context
from django.test import TestCase
from django.forms import formset_factory
from djgentelella.views.storyline import OptionsSerializer
from djgentelella.widgets.storyline import UrlStoryLineInput
from django import forms


attrs={"data-url": 'examplestoryline-url/',  "height": 568}


class FormClass(forms.Form):
    storyline = forms.CharField(widget=UrlStoryLineInput(attrs))

class MultiItemsFormClass(forms.Form):
    storyone = forms.CharField(widget=UrlStoryLineInput(attrs), disabled=True, required=True)
    storytwo = forms.CharField(widget=UrlStoryLineInput(attrs), disabled=True, required=False)
    storythree = forms.CharField(widget=UrlStoryLineInput(attrs), disabled=False, required=False)


class UrlStorylineWidgetUnitTest(TestCase):

    def render(self, msg, context={}):
        template = Template(msg)
        context = Context(context)
        return template.render(context)

    def setUp(self):
        self.basicform = FormClass()
        self.prefixform = FormClass(prefix='newname')
        self.multiitemsform = MultiItemsFormClass()

    def test_check_names(self):
        """
        This test check how to deal with names and ids in the widget.
        reason: Names could be modify in templates accidentally.
        """
        noprefix = self.render('{{form}}', {'form': self.basicform})
        withprefix = self.render('{{form}}', {'form': self.prefixform})

        self.assertIn('id="id_storyline"', noprefix)
        self.assertIn('id="id_newname-storyline"', withprefix)
        # Name is not relevant now
        # self.assertIn('name="storyline"', noprefix)
        # self.assertIn('name="newname-storyline"', withprefix)

    def test_check_disable_required(self):
        """
        required and disabled are fields not required because widget is readonly.
        reason:  required prevent form submit and disabled can change css behaviour.
        """
        form = self.render('{{form}}', {'form': self.multiitemsform})
        self.assertNotIn("required", form)
        self.assertNotIn("disabled", form)

    def test_check_datawidget(self):
        """
        check that data-widget is present in the form render
        reason:  required prevent form submit and disabled can change css behaviour.
        """
        form = self.render('{{form}}', {'form': self.basicform})
        self.assertIn('data-widget="UrlStoryLineInput"', form)


    def test_check_data_url_required(self):
        """
        Check exception when data-url not found on widget
        reason: help user to identify error when code
        """

        with self.assertRaisesRegex(ImproperlyConfigured, "You must add data-url on attrs"):
            class InvalidForm(forms.Form):
                storyline = forms.CharField(widget=UrlStoryLineInput)
                storytwo = forms.CharField(widget=UrlStoryLineInput({"height": 20}))

    def test_widget_formset(self):
        storyLineFormSet = formset_factory(FormClass, extra=2)
        formset = storyLineFormSet()
        for formIndex in range(len(formset)):
            form_str = self.render('{{form}}', {'form': formset[formIndex]})
            self.assertIn(f'id_form-{formIndex}-storyline', form_str)
            self.assertNotIn("required", form_str)
            self.assertNotIn("disabled", form_str)
            self.assertIn('data-widget="UrlStoryLineInput"', form_str)


class SerializerCheckTest(TestCase):
    def setUp(self):
        self.data = {
            "url": 'myurl/',
            "datetime_column_name": "date",
            "datetime_format": "%Y-%m-%d",
            "data_column_name": "income"}

        self.invalid_data_1 = {
            "datetime_format": "%Y-%m-%d",
            "data_column_name": "income"
        }
        self.invalid_data_2 = {
            "datetime_column_name": "date",
            "datetime_format": "%Y-%m-%d"
        }
        self.invalid_data_3 = {
            "datetime_column_name": "date",
            "data_column_name": "income"
        }

        self.chart = {
            "datetime_format": "%Y",
            "y_axis_label": "Income"
        }
        self.invalid_chart = {
            "y_axis_label": "Income"
        }

        self.slider = {
            "start_at_card": "1",
            "title_column_name": "title",
            "text_column_name": "text",
        }
        self.invalid_slider_1 = {
            "start_at_card": "1",
            "text_column_name": "text",
        }
        self.invalid_slider_2 = {
            "start_at_card": "1",
            "title_column_name": "title",
        }

        self.options = {
            "data": self.data,
            "chart": self.chart,
            "slider": self.slider
        }

    def test_OptionsSerializer_data(self):
        """
        Check correct data validation on data field.
        reason: we need to identify possible data errors in serializer
        """
        bad_data = {'data': self.invalid_data_1,'chart': self.chart,'slider': self.slider}
        new_serializer = OptionsSerializer(data=bad_data)
        self.assertEqual(new_serializer.is_valid(), False)
        error_list = list(new_serializer.errors['data'].keys())
        wait_list = ['datetime_column_name', 'url']
        error_list.sort()
        wait_list.sort()
        self.assertListEqual(error_list, wait_list)

        bad_data = {'data': self.invalid_data_2, 'chart': self.chart,'slider': self.slider}
        new_serializer = OptionsSerializer(data=bad_data)
        self.assertEqual(new_serializer.is_valid(), False)
        error_list = list(new_serializer.errors['data'].keys())
        wait_list = ['data_column_name', 'url']
        error_list.sort()
        wait_list.sort()
        self.assertListEqual(error_list, wait_list)

        bad_data = {'data': self.invalid_data_3,'chart': self.chart,'slider': self.slider}
        new_serializer = OptionsSerializer(data=bad_data)
        self.assertEqual(new_serializer.is_valid(), False)
        error_list = list(new_serializer.errors['data'].keys())
        wait_list = ['datetime_format', 'url']
        error_list.sort()
        wait_list.sort()
        self.assertListEqual(error_list, wait_list)

    def test_OptionsSerializer_chart(self):
        """
        Check chart structure data, this test checks that  datetime_format not found.
        reason: Js doesn't work if datetime_format is not present
        """
        bad_data = {'data': self.data, 'chart': self.invalid_chart, 'slider': self.slider}
        new_serializer = OptionsSerializer(data=bad_data)
        self.assertEqual(new_serializer.is_valid(), False)
        error_list = list(new_serializer.errors['chart'].keys())
        wait_list = ['datetime_format']
        self.assertListEqual(error_list, wait_list)


    def test_OptionsSerializer_slider(self):
        """
        Check validation of slider with wrong data.
        reason: slider can generate JS issues when data has the incorrect parameters

        """

        bad_data = {'data': self.data,'chart': self.chart,'slider': self.invalid_slider_1}
        new_serializer = OptionsSerializer(data=bad_data)
        self.assertEqual(new_serializer.is_valid(), False)
        error_list = list(new_serializer.errors['slider'].keys())
        wait_list = ['title_column_name']
        self.assertListEqual(error_list, wait_list)

        bad_data = {'data': self.data, 'chart': self.chart,'slider': self.invalid_slider_2}
        new_serializer = OptionsSerializer(data=bad_data)
        self.assertEqual(new_serializer.is_valid(), False)
        error_list = list(new_serializer.errors['slider'].keys())
        wait_list = ['text_column_name']
        self.assertListEqual(error_list, wait_list)




    def test_OptionsSerializer_valid(self):
        """This test checks that the serializer works with all configurations possible
        FIXME: better data options required that can check all configurations available
        reason: check the correct way.
        """
        data = {'data': self.data,'chart': self.chart,'slider': self.slider}
        new_serializer = OptionsSerializer(data=data)
        self.assertEqual(new_serializer.is_valid(), True)