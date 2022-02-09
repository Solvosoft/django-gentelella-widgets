from django.core.exceptions import ImproperlyConfigured
from django.template import Template, Context
from django.test import TestCase
from django.forms import formset_factory
from django import forms

from djgentelella.widgets.timeline import UrlTimeLineInput

attrs={"data-url": 'exampletimeline-url/',  "height": 568}


class FormClass(forms.Form):
    timeline = forms.CharField(widget=UrlTimeLineInput(attrs))

class MultiItemsFormClass(forms.Form):
    timelineone = forms.CharField(widget=UrlTimeLineInput(attrs), disabled=True, required=True)
    timelinetwo = forms.CharField(widget=UrlTimeLineInput(attrs), disabled=True, required=False)
    timelinethree = forms.CharField(widget=UrlTimeLineInput(attrs), disabled=False, required=False)


class UrlTimeWidgetUnitTest(TestCase):

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

        self.assertIn('id="id_timeline"', noprefix)
        self.assertIn('id="id_newname-timeline"', withprefix)
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
        self.assertIn('data-widget="UrlTimeLineInput"', form)

    def test_check_data_url_required(self):
        """
        Check exception when data-url not found on widget
        reason: help user to identify error when code
        """

        with self.assertRaisesRegex(ImproperlyConfigured, "You must add data-url on attrs"):
            class InvalidForm(forms.Form):
                storyline = forms.CharField(widget=UrlTimeLineInput)
                storytwo = forms.CharField(widget=UrlTimeLineInput({"height": 20}))

    def test_widget_formset(self):
        timeLineFormSet = formset_factory(FormClass, extra=2)
        formset = timeLineFormSet()
        for formIndex in range(len(formset)):
            form_str = self.render('{{form}}', {'form': formset[formIndex]})
            self.assertIn(f'id_form-{formIndex}-timeline', form_str)
            self.assertNotIn("required", form_str)
            self.assertNotIn("disabled", form_str)
            self.assertIn('data-widget="UrlTimeLineInput"', form_str)

