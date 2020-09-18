from django import forms
from demoapp import models
from djgentelella.forms.forms import GTForm

from django.forms import widgets, TextInput, MultiWidget
from datetime import date
from djgentelella.widgets import core as widget



class ContactForm(forms.ModelForm, GTForm):

    class Meta:
        model = models.Contact
        fields = '__all__'
        widgets = {
            'number': widget.PhoneNumberWidget()       
             }
