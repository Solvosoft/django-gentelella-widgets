from django import forms
from demoapp import models
from djgentelella.forms.forms import CustomForm
from djgentelella.widgets import core as widget


class DateRangeForms(forms.ModelForm, CustomForm):

    class Meta:
        model = models.DateRange
        fields = '__all__'
        widgets = {
            'name': widget.TextInput,
            'date': widget.DateRangeInput,
            'date_start': widget.DateRangeInputSingle,
            'date_end': widget.DateRangeInputSingle,
            'date_time': widget.DateRangeInputSingle,
        }

