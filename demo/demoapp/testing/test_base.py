from django.test import TestCase, SimpleTestCase
from django.forms.renderers import DjangoTemplates

class WidgetTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        cls.django_renderer = DjangoTemplates()
        super().setUpClass()

    def check_html(self, widget, name, value, html='', attrs=None, strict=False, **kwargs):
        assertEqual = self.assertEqual if strict else self.assertHTMLEqual
        output = widget.render(name, value, attrs=attrs,
                               renderer=self.django_renderer, **kwargs)
        assertEqual(output, html)

    def check_type(self, widget, data_type):
        widget = widget.input_type
        self.assertEquals(widget, data_type)

    def check_render_none(self, widget, html):
        self.check_html(widget, '', None,
                        html=html)

    def check_value_size(self, widget,value, size):

        attrs = widget.get_context(name='name', value=None, attrs={})[
            'widget']['attrs']
        attrs['value']=value
        
        self.assertEquals(len(attrs['value']), size)

    def check_find_at_Sign(self,widget, value):

        attrs = widget.get_context(name='name', value=None, attrs={'value':value})[
            'widget']['attrs']
        
        self.assertNotEquals(attrs['value'].find('@'), -1)

    def check_attrs(self, widget, attrs={}):
        self.assertEquals(widget.attrs, attrs)

    def check_constructor_attrs(self, widget, attrs):
        attributes = widget.get_context(name='name', value=None, attrs={})[
            'widget']['attrs']
        self.assertEquals(attributes, attrs)

    def check_render_custom_attrs(self, widget, name, value, attrs, html):
        self.check_html(widget, name, value, attrs=attrs,
                        html=html,)

    
    def check_template_name(self,widget,template_name):
        template = widget.template_name
        self.assertEqual(template, template_name)           
   
    def check_value_output(self, widget,name, value):

        attrs = widget.get_context(name=name, value=None, attrs={'value':value})['widget']['attrs']
        self.assertEquals(attrs['value'], value)
        output = self.widget.render(name, None, attrs={
                                    'value': attrs['value']}, renderer=self.django_renderer)
        self.assertHTMLEqual(
            output, '<input type="%s" name="%s" class="%s" data-widget="%s" value="%s">'%('text',name,attrs['class'],attrs['data-widget'],value))

