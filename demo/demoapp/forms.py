from django import forms
from djgentelella.forms.forms import CustomForm
from .models import Foo
from djgentelella.widgets import numberknobinput as knobwidget


class FooForm(forms.ModelForm):
    class Meta:
        model = Foo
        fields = ['number_of_eyes']

class RawFooForm(forms.Form):
    age = forms.IntegerField(
            widget=knobwidget.NumberKnobInput(attrs={
                                      "value": 5,
                                      "data-min":1,
                                      "data-max":120}))
    speed_in_miles_per_hour = forms.FloatField(
                                widget=knobwidget.NumberKnobInput(attrs={
                                                          "value": 5,
                                                          "data-min":1,
                                                          "data-step": 0.1,
                                                          "data-max":50}))
    number_of_eyes = forms.IntegerField(
                        widget=knobwidget.NumberKnobInput(attrs={
                                                  "value": 5,
                                                  "data-min":1,
                                                  "steps": 0.1,
                                                  "data-max":50}))