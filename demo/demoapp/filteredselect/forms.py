from django import forms

from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as genwidgets
from djgentelella.widgets.selectmultiple import FilteredSelectMultiple

from demoapp.models import PeopleGroup


class PeopleGroupFilteredForm(GTForm, forms.ModelForm):
    """Both many to many fields fed by a gtselects endpoint.

    `personbasename` also answers with disabled entries, which is what makes
    this a useful demo: a disabled option has to stay put when the arrows or
    "choose all" run.
    """

    class Meta:
        model = PeopleGroup
        fields = ['name', 'people', 'communities']
        widgets = {
            'name': genwidgets.TextInput,
            'people': FilteredSelectMultiple(
                url='personbasename', verbose_name='people'
            ),
            'communities': FilteredSelectMultiple(
                url='communitybasename', verbose_name='communities'
            ),
        }


class StaticChoicesForm(GTForm, forms.Form):
    """No endpoint: the options come from `choices`, grouped in optgroups.

    Everything is rendered inside the real select and the javascript splits it,
    so the field still works with javascript off.
    """

    languages = forms.MultipleChoiceField(
        label='Languages',
        required=False,
        choices=[
            (
                'Compiled',
                [('c', 'C'), ('go', 'Go'), ('rs', 'Rust')],
            ),
            (
                'Interpreted',
                [('py', 'Python'), ('rb', 'Ruby'), ('js', 'JavaScript')],
            ),
        ],
        widget=FilteredSelectMultiple(verbose_name='languages'),
    )
