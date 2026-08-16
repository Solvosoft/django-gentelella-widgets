from django import forms

from djgentelella.forms.forms import GTForm
from djgentelella.widgets.maps import MapPointInput

from demoapp.models import Place


class PlaceForm(GTForm, forms.ModelForm):
    """The model field brings its own configured widget along."""

    class Meta:
        model = Place
        fields = ["name", "country", "city", "location"]


class SimplePointForm(GTForm, forms.Form):
    """The widget used on its own, without the model field."""

    location = forms.CharField(
        label="Location",
        required=False,
        widget=MapPointInput(zoom=8, center=(9.9327, -84.0875), search=True),
    )
