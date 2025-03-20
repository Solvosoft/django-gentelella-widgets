from django import forms

from demoapp import models


class MultiWidgetForm(forms.ModelForm):
    class Meta:
        model = models.MultiWidgetModel
        fields = '__all__'
