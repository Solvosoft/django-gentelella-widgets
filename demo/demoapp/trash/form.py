from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as gtw

from django import forms
from demoapp.models import Customer

class CustomerForm(GTForm, forms.ModelForm):
    class Meta:
        model = Customer
        fields = "__all__"
        exclude = ["is_deleted"]
        widgets = {
            "name": gtw.TextInput,
            "email": gtw.EmailInput,
            "phone_number": gtw.PhoneNumberMaskInput,
        }

