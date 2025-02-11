from django import forms

from demoapp.models import Person
from djgentelella.forms.forms import GTForm


class CardListPerson(GTForm, forms.ModelForm):
    class Meta:
        model = Person
        fields = '__all__'
