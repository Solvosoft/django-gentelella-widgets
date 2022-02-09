from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from django import forms

from djgentelella.widgets.storymap import GigaPixelStoryMapInput, MapBasedStoryMapInput
from django.template import Template, Context
from django.forms import formset_factory
attrs={"data-url": 'storymap-url/'}


class FormClass(forms.Form):
    gp_storymap = forms.CharField(widget=GigaPixelStoryMapInput(attrs), required=False)
    mb_storymap = forms.CharField(widget=MapBasedStoryMapInput(attrs), disabled=True)


class MultiItemsFormClass(forms.Form):
    gigapixelone = forms.CharField(widget=GigaPixelStoryMapInput(attrs), disabled=True, required=True)
    gigapixeltwo = forms.CharField(widget=GigaPixelStoryMapInput(attrs), disabled=True, required=False)
    gigapixelthree = forms.CharField(widget=GigaPixelStoryMapInput(attrs), disabled=False, required=False)

    mapbasedone = forms.CharField(widget=MapBasedStoryMapInput(attrs), disabled=True, required=True)
    mapbasedtwo = forms.CharField(widget=MapBasedStoryMapInput(attrs), disabled=True, required=False)
    mapbasedthree = forms.CharField(widget=MapBasedStoryMapInput(attrs), disabled=False, required=False)


class StoryMapFormWidgetTest(TestCase):

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

        self.assertIn('id="id_gp_storymap"', noprefix)
        self.assertIn('id="id_newname-gp_storymap"', withprefix)
        self.assertIn('id="id_mb_storymap"', noprefix)
        self.assertIn('id="id_newname-mb_storymap"', withprefix)


    def test_check_disable_required(self):
        """
        required and disabled are fields not required because widget is readonly.
        reason:  required prevent form submit and disabled can change css behaviour.
        """
        form = self.render('{{form}}', {'form': self.multiitemsform})
        self.assertNotIn("required", form)
        self.assertNotIn("disabled", form)

    def test_check_data_url_required(self):
        """
        Check exception when data-url not found on widget
        reason: help user to identify error when code
        """

        with self.assertRaisesRegex(ImproperlyConfigured, "You must add data-url on attrs"):
            class InvalidForm(forms.Form):
                storyline = forms.CharField(widget=MapBasedStoryMapInput)
                storytwo = forms.CharField(widget=GigaPixelStoryMapInput)


    def test_widget_formset(self):
        gigaPixelStoryMapFormSet = formset_factory(FormClass, extra=2)
        formset = gigaPixelStoryMapFormSet()
        form_str = self.render('{{form}}', {'form': formset})
        for formIndex in range(len(formset)):
            self.assertIn(f'id_form-{formIndex}-gp_storymap', form_str)
            self.assertIn(f'id_form-{formIndex}-mb_storymap', form_str)
       # managementform
       # self.assertIn(f'id_form-_PREFIX_-gp_storymap', form_str)
       # self.assertIn(f'id_form-_PREFIX_-mb_storymap', form_str)
        self.assertNotIn("required", form_str)
        self.assertNotIn("disabled", form_str)
        self.assertIn('data-widget="GigaPixelStoryMapInput"', form_str)
        self.assertIn('data-widget="MapBasedStoryMapInput"', form_str)
