from django import forms

from demoapp import models
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as widget


class InputMaskForms(forms.ModelForm, GTForm):
    grid_representation = [
        [['date'], ['phone']],
        [['serial_number'], ['taxid']],
        [['credit_card'], ['email']],
    ]

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
