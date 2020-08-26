from django import forms
from demoapp import models
from djgentelella.forms.forms import CustomForm
from djgentelella.widgets import core as widget


class InputMaskForms(forms.ModelForm,CustomForm):
    
    class Meta:
        model= models.InputMask
        fields='__all__'
        widgets={
            'phone': widget.PhoneNumberMaskInput,
            'custom': widget.CustomMaskInput,
            'date': widget.DateMaskInput,
            'serial_number': widget.SerialNumberMaskInput,
            'taxid': widget.TaxIDMaskInput,
            'credit_card':widget.CreditCardMaskInput
        }
        
