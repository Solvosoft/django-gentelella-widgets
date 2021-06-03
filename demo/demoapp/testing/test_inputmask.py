from djgentelella.widgets import core as widgets
from datetime import datetime,date
from .test_base import WidgetTest

class DateMask(WidgetTest):
    widget = widgets.DateMaskInput()
    def test_format(self):
        format = self.widget.format_key
        self.assertEqual(format, 'DATE_FORMAT')
  
    def test_render_none(self):
        self.check_html(self.widget, 'date', None,
                        html='<input type="text" class="form-control" data-widget="DateMaskInput" name="date">')

    def test_string(self):
        self.check_html(self.widget, 'date', '2020-12-31', html=(
            '<input type="text" name="date" class="form-control" data-widget="DateMaskInput" value="2020-12-31">'))

    def test_template_name(self):    
        self.check_template_name(self.widget,'gentelella/widgets/date_input_mask.html')

    def test_type(self):    
        self.check_type(self.widget,'text')


class PhoneNumberMask(WidgetTest):
    widget = widgets.PhoneNumberMaskInput()

    def test_type(self):
        self.check_type(self.widget,'text')

    def test_render_none(self):
        self.check_render_none(self.widget,'<input type="text" class="form-control" data-widget="PhoneNumberMaskInput" name="">')

    def test_value_output(self):
        self.check_value_output(self.widget,'phone','8999-00-00')

    def test_value_size(self):
        self.check_value_size(self.widget,'8920-3214',9)

    def test_attrs(self):
        self.assertEquals(self.widget.attrs, {'class': 'form-control ',
                                              'data-widget': 'PhoneNumberMaskInput'})

    def test_constructor_attrs(self):
        self.check_constructor_attrs(self.widget,{'class': 'form-control ','data-widget': 'PhoneNumberMaskInput'})

    def test_render_custom_attrs(self):
        self.check_render_custom_attrs(self.widget,'phone','(505)8948-62-29',{'class': 'phones'},
                                       '<input type="text" name="phone" data-widget="PhoneNumberMaskInput" value="(505)8948-62-29" class="phones">')

    def test_template_name(self):    
        self.check_template_name(self.widget,'gentelella/widgets/input_mask.html')

class TaxIDMaskInput(WidgetTest):
    widget = widgets.TaxIDMaskInput()

    def test_type(self):
        self.check_type(self.widget,'text')

    def test_render_none(self):
        self.check_render_none(self.widget,'<input type="text" class="form-control" data-widget="TaxIDMaskInput" name="">')

    def test_value_output(self, **kwargs):
        self.check_value_output(self.widget,'taxid','113-3141')

    def test_value_size(self, **kwargs):
        self.check_value_size(self.widget,'31141',5)

    def test_constructor_attrs(self):
        self.check_constructor_attrs(self.widget, {'class': 'form-control ',
                                  'data-widget': 'TaxIDMaskInput'})

    def test_render_custom_attrs(self):
        self.check_html(self.widget, 'taxid', '12-314', attrs={'class': 'tax'},
                        html='<input type="text" name="taxid" data-widget="TaxIDMaskInput" value="12-314" class="tax">',
                        )
    def test_template_name(self):    
        self.check_template_name(self.widget,'gentelella/widgets/input_mask.html')


class SerialNumberMaskInputTest(WidgetTest):
    widget = widgets.SerialNumberMaskInput()

    def test_type(self):
        self.check_type(self.widget,'text')   
    def test_render_none(self):
        self.check_render_none(self.widget,'<input type="text" class="form-control" data-widget="SerialNumberMaskInput" name="">')

    def test_value_output(self, **kwargs):
        self.check_value_output(self.widget,'serial','31141')
   
    def test_value_size(self, **kwargs):
        self.check_value_size(self.widget,'414-45267',9)

    def test_constructor_attrs(self):
        self.check_constructor_attrs(self.widget,{'class': 'form-control ','data-widget': 'SerialNumberMaskInput'})

    def test_render_custom_attrs(self):
        self.check_render_custom_attrs(self.widget,'serial','33-2131',{'class':'serial'},
                                       '<input type="text" name="serial" data-widget="SerialNumberMaskInput" value="33-2131" class="serial">',
                                          )
    def test_template_name(self):    
        self.check_template_name(self.widget,'gentelella/widgets/input_mask.html')

class CreditCardMaskInputTest(WidgetTest):
    widget = widgets.CreditCardMaskInput()

    def test_type(self):
        self.check_type(self.widget,'text')

    def test_render_none(self):
        self.check_render_none(self.widget,'<input type="text" class="form-control" data-widget="CreditCardMaskInput" name="">')

    def test_value_output(self):
        self.check_value_output(self.widget,'credit','31141')
    
    def test_value_size(self, **kwargs):
        self.check_value_size(self.widget,'414-45267',9)

    def test_constructor_attrs(self):
        self.check_constructor_attrs(self.widget,{'class': 'form-control ','data-widget': 'CreditCardMaskInput'})
        
    def test_render_custom_attrs(self):
        self.check_render_custom_attrs(self.widget, 'credit', '33-2131',{'class': 'credit'}, 
                                       '<input type="text" name="credit" data-widget="CreditCardMaskInput" value="33-2131" class="credit">')
    def test_template_name(self):    
        self.check_template_name(self.widget,'gentelella/widgets/input_mask.html')

class EmailMaskInputTest(WidgetTest):
    widget = widgets.EmailMaskInput()

    def test_type(self):
        self.check_type(self.widget, 'text')

    def test_render_none(self):
        self.check_render_none(
            self.widget, '<input type="text" class="form-control" data-widget="EmailMaskInput" name="">')

    def test_value_output(self): 
      self.check_value_output(self.widget,'email','J@gmail.com' )     
     
    def test_value_size(self):
        self.check_value_size(self.widget,'414-45267', 9)

    def test_find_at_Sign(self):
        self.check_find_at_Sign(self.widget,'ksjifason@gmail.com')

    def test_attrs(self):
        self.check_attrs(self.widget,{'class': 'form-control ','data-widget': 'EmailMaskInput'})

    def test_render_custom_attrs(self):
        self.check_render_custom_attrs(self.widget,'email','kenjen@gmail.com',{'class':'email'},
                                       '<input type="text" name="email" data-widget="EmailMaskInput" value="kenjen@gmail.com" class="email">')
    def test_template_name(self):    
        self.check_template_name(self.widget,'gentelella/widgets/email_input_mask.html')

