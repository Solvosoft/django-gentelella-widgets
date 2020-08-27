from django import forms
from demoapp import models
from djgentelella.forms.forms import CustomForm
from djgentelella.widgets import core as widget
from django.core.exceptions import ValidationError


class InputMaskForms(forms.ModelForm, CustomForm):

    class Meta:
        model = models.InputMask
        fields = '__all__'
        widgets = {
            'phone': widget.PhoneNumberMaskInput,
            'custom': widget.CustomMaskInput,
            'date': widget.DateMaskInput,
            'serial_number': widget.SerialNumberMaskInput,
            'taxid': widget.TaxIDMaskInput,
            'credit_card': widget.CreditCardMaskInput
        }

    def clean_phone(self):
        phone=self.cleaned_data["phone"]
        if len(phone) < 14:
            raise phone.ValidationError('at least 14 digits')
        return phone
    
    def clean_serial_number(self):
        serial_number=self.cleaned_data["serial_number"]
        if len(serial_number) < 23:
            raise serial_number.ValidationError('at least 23 digits')
        return serial_number
    
    def clean_custom(self):
        custom=self.cleaned_data["custom"]
        if len(custom) < 9:
            raise custom.ValidationError('at least 9 digits')
        return custom
    
    def clean_taxid(self):
        taxid=self.cleaned_data['taxid']
        if len(taxid) < 11:
            raise taxid.ValidationError('at least 11 digits')
        return taxid
    
    def clean_credit_card(self):
        credit_card=self.cleaned_data["credit_card"]
        if len(credit_card) < 19:
            raise credit_card.ValidationError('at least 19 digits')
        return credit_card