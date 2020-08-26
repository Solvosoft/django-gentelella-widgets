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
        data = self.cleaned_data["phone"]
        if len(self.data) < 14:
            raise forms.ValidationError('at least 14 digits')

    def clean_serial_number(self):
        data = self.cleaned_data["serial_number"]
        if len(self.data) < 23:
            raise forms.ValidationError('at least 23 digits')

    def clean_taxid(self):
        data = self.cleaned_data["taxid"]
        if len(self.data) < 11:
            raise forms.ValidationError('at least 11 digits')

    def clean_credit_card(self):
        data = self.cleaned_data["credit_card"]
        if len(self.data) < 19:
            raise forms.ValidationError('at least 19 digits')
