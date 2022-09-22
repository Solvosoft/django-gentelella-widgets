from django.urls import reverse_lazy

from djgentelella.forms.forms import GTForm
from django import forms

from djgentelella.widgets.storyline import UrlStoryLineInput


class StoryLineForm(GTForm, forms.Form):
    storyline = forms.CharField(widget=UrlStoryLineInput(
        attrs={"data-url": reverse_lazy('examplestoryline-list'),
               "height": 568}
    ))