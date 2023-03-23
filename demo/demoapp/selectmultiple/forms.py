from django import forms
from demoapp.models import selectModel

class dataOptions(forms.Form):
    desc = forms.CharField(max_length=200, required=True)
