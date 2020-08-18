from django import forms
from djgentelella.forms.forms import CustomForm
from djgentelella.widgets.core import DateTimeInput, DateInput
from djgentelella.widgets.selects import AutocompleteSelect
from .models import Foo, Person
from djgentelella.widgets import numberknobinput as knobwidget
from djgentelella.widgets.color import StyleColorInput, DefaultColorInput, HorizontalBarColorInput, VerticalBarColorInput, InlinePickerColor
from demoapp.models import Colors


class FooModelForm(CustomForm, forms.ModelForm):
    class Meta:
        model = Foo
        fields = ('number_of_eyes', 
                  'speed_in_miles_per_hour',
                  'age')
        widgets = {
            'number_of_eyes': knobwidget.NumberKnobInput(attrs={}),
            'speed_in_miles_per_hour': knobwidget.NumberKnobInput(
                                            attrs={
                                                "data-min": 1,
                                                "data-step": 0.1,
                                                "data-max": 50
                                            }),
            'age': knobwidget.NumberKnobInput()
        }


class FooBasicForm(CustomForm, forms.Form):
    """creates a basic form with three widgets using different attrs"""
    age = forms.IntegerField(
            widget=knobwidget.NumberKnobInput(attrs={}), initial=15)
    speed_in_miles_per_hour = forms.FloatField(
                                widget=knobwidget.NumberKnobInput(attrs={
                                                          "data-min":1,
                                                          "data-step": 0.1,
                                                          "data-max":50}))
    number_of_eyes = forms.IntegerField(
                        widget=knobwidget.NumberKnobInput(attrs={
                                                  "data-min":1,
                                                  "steps": 0.1,
                                                  "data-max":50}))


class ColorWidgetsForm(CustomForm, forms.ModelForm):
    color = forms.CharField(widget=DefaultColorInput)
    color2 = forms.CharField(widget=StyleColorInput(attrs={"value": "#0014bb", "id": "c2"}))

    class Meta:
        model = Colors
        fields = "__all__"
        widgets = {
            "color3": HorizontalBarColorInput,
            "color4": VerticalBarColorInput(attrs={"value": "#0014bb", "id": "c4"}),
        }


class SimpleColorForm(CustomForm, forms.Form):
    default_input = forms.CharField(
        widget=DefaultColorInput
    )
    style_input = forms.CharField(
        widget=StyleColorInput(attrs={"value": "#0014bb"})
    )
    horizontal_bar_input = forms.CharField(
         widget=HorizontalBarColorInput
    )
    vertical_bar_input = forms.CharField(
         widget=VerticalBarColorInput(attrs={"value": "#0014bb"})
    )
    inline_picker = forms.CharField(
         widget=InlinePickerColor
    )


class PersonForm(CustomForm, forms.ModelForm):
    class Meta:
        model = Person
        fields = '__all__'
        widgets = {
            'country': AutocompleteSelect('countrybasename'),
            'last_time': DateTimeInput,
            'born_date': DateInput
        }