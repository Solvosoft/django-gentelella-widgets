from djgentelella.forms.forms import CustomForm
from djgentelella.widgets import core as genwidgets
from django import forms


class InputMaskForm(CustomForm):
    date_mask= forms.DateField(label="Date Mask",widget=genwidgets.DateMaskInput)
    phone_mask= forms.CharField(label="Phone Mask", widget=genwidgets.PhoneNumberMaskInput)
    custom_mask= forms.CharField(label="Custom Mask", widget=genwidgets.CustomMaskInput)
    serial_number= forms.CharField(label="Serial Number Mask", widget=genwidgets.SerialNumberMaskInput)
    credit_Card_mask = forms.CharField(label="Credit Card Mask",widget=genwidgets.CreditMaskInput)
    taxID_mask= forms.CharField(label="TaxID Mask", widget=genwidgets.TaxIDMaskInput)