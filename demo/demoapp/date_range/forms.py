from django import forms
from demoapp import models
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as widget


class DateRangeForms(forms.ModelForm, GTForm):

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

