from django import forms

from demoapp.models import NewHire
from djgentelella.forms.forms import GTForm, UserScopedUploadsMixin
from djgentelella.widgets import core as genwidgets
from djgentelella.widgets.files import UserFileChunkedUpload


class PersonalForm(GTForm, forms.ModelForm):
    class Meta:
        model = NewHire
        fields = ['name', 'email', 'birth_date', 'has_car']
        widgets = {'name': genwidgets.TextInput, 'email': genwidgets.EmailInput,
                   'birth_date': genwidgets.DateInput,
                   'has_car': genwidgets.YesNoInput}


class VehicleForm(GTForm, forms.ModelForm):
    class Meta:
        model = NewHire
        fields = ['car_plate']
        widgets = {'car_plate': genwidgets.TextInput}

    def clean_car_plate(self):
        plate = self.cleaned_data['car_plate'].strip().upper()
        if not plate:
            raise forms.ValidationError(forms.Field.default_error_messages['required'])
        return plate


class JobForm(UserScopedUploadsMixin, GTForm, forms.ModelForm):
    class Meta:
        model = NewHire
        fields = ['department', 'start_date', 'contract']
        widgets = {'department': genwidgets.Select,
                   'start_date': genwidgets.DateInput,
                   'contract': UserFileChunkedUpload}
