from django import forms

from djgentelella.forms.forms import GTForm
from djgentelella.models import MenuItem
from djgentelella.widgets.core import Select2Box

class dataOptions(GTForm):
    mydata = forms.ChoiceField(widget=Select2Box, choices=[[1, "primero"], [2, "segundo"], [3, "tercero"]])
    mymenu = forms.ModelMultipleChoiceField(widget=Select2Box(attrs={'data-url':'https://pokeapi.co/api/v2/pokemon/?limit=10'}), queryset=MenuItem.objects.all())
    mydataTest = forms.ChoiceField(widget=Select2Box, choices=[[1, "primero"], [2, "segundo"], [3, "tercero"]])
