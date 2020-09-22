from django import forms
from demoapp import models
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as widget



class ExampleForm(forms.ModelForm, GTForm):

    class Meta:
        model = models.Multiwidget
        fields = '__all__'
        widgets = {
            'phone_number': widget.PhoneNumberMultiWidget,       
            'passport':widget.PassportWidget,
            'date':widget.SplitDateMultiWidget
             }
