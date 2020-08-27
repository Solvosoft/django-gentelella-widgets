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
        phone = self.cleaned_data["phone"]
        if phone.find('_') != -1:
            raise forms.ValidationError('at least 14 digits')
        else:
            return phone

    def clean_serial_number(self):
        serial_number = self.cleaned_data["serial_number"]
        if serial_number.find('_') != -1:
            raise forms.ValidationError('at least 23 digits')
        else:
            return serial_number

    def clean_custom(self):
        custom = self.cleaned_data["custom"]
        if custom.find('_') != -1:
            raise forms.ValidationError('at least 9 digits')
        else:
            return custom

    def clean_taxid(self):
        taxid = self.cleaned_data['taxid']
        if taxid.find('_') != -1:
            raise forms.ValidationError('at least 11 digits')
        return taxid

    def clean_credit_card(self):
        credit_card = self.cleaned_data["credit_card"]
        if credit_card.find('_') != -1:
            raise forms.ValidationError('at least 19 digits')
        else:
            return credit_card
