from django import forms
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as genwidgets
from django.utils.translation import gettext_lazy as _


class HistoryFilterForm(GTForm, forms.Form):
    category = forms.ChoiceField(
        choices=[
            ("--------", _("All")),
            ("demoapp.customer", _("Customer")),
            ("djgentelella.trash", _("Trash")),
            # add more categories here
        ],
        widget=genwidgets.Select,
        label=_("Category"),
    )

