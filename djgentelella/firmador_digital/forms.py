from django import forms
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as genwidgets
from django.utils.translation import gettext_lazy as _

class CardForm(GTForm):
    card = forms.ChoiceField(choices=[], widget=genwidgets.Select, label=_("Card"))
    organization = forms.CharField(widget=genwidgets.HiddenInput)
    instance = forms.CharField(widget=genwidgets.HiddenInput)
