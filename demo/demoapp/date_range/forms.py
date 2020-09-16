from django import forms
from demoapp import models
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as widget


class DateRangeForms(forms.ModelForm, GTForm):

    class Meta:
        model = models.DateRange
        fields = '__all__'
        widgets = {
            'date_range': widget.DateRangeInput,
            'date_custom': widget.DateRangeInputCustom,
            'date_time': widget.DateRangeTimeInput,
        }

