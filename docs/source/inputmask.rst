======================
InputMask widget
======================

.. image:: _static/InputMask.png
  

It is a kind of mask to input date, email and text values.
You can uses this widget in a *DateField*, *CharField* , *EmailField*

.. code:: python
from djgentelella.widgets import core as widget 

class InputMaskForms(forms.ModelForm, CustomForm):

    class Meta:
        model = models.InputMask
        fields = '__all__'
        widgets = {
            'phone': widget.PhoneNumberMaskInput,
            'date': widget.DateMaskInput,
            'serial_number': widget.SerialNumberMaskInput,
            'taxid': widget.TaxIDMaskInput,
            'credit_card': widget.CreditCardMaskInput, 
            'email': widget.EmailMaskInput,
        }


Exist six types of InputMask widget: **PhoneNumberMaskInput, DateMaskInput, SerialNumberMaskInput, TaxIDMaskInput,CreditCardMaskInput,EmailMaskInput**
