"""Forms without ``dynamic_actions``, rendered by the snapshot test.

The HTML each one renders was captured in ``tests/snapshots/`` *before* the
dynamic actions existed. A form that declares none must keep rendering byte
for byte the same, in every render of GTForm and inside a formset.
"""

from django import forms
from django.forms import formset_factory

from djgentelella.forms.forms import GTForm, GTFormSet
from djgentelella.widgets import core as genwidgets

SNAPSHOT_RENDERS = ('as_plain', 'as_inline', 'as_horizontal', 'as_grid')


class SnapshotForm(GTForm):
    grid_representation = [[['name', 'kind'], ['amount']], [['born', 'active']]]

    name = forms.CharField(
        label='Name', help_text='Your <b>name</b>', widget=genwidgets.TextInput)
    kind = forms.ChoiceField(
        choices=[('a', 'A'), ('b', 'B')], widget=genwidgets.Select)
    amount = forms.DecimalField(required=False, widget=genwidgets.NumberInput)
    # A TextInput: DateInput bakes the language active at import into the html.
    born = forms.DateField(required=False, widget=genwidgets.TextInput)
    active = forms.BooleanField(required=False, widget=genwidgets.YesNoInput)
    secret = forms.CharField(required=False, widget=genwidgets.HiddenInput)


SnapshotFormSet = formset_factory(SnapshotForm, formset=GTFormSet, extra=2)


def snapshot_renders():
    """``{snapshot name: html}`` for everything the snapshot test compares."""
    result = {}
    for render in SNAPSHOT_RENDERS:
        result['unbound_%s' % render] = str(getattr(SnapshotForm(), render)())
        bound = SnapshotForm(data={'name': '', 'kind': 'zz'}, prefix='p')
        result['bound_%s' % render] = str(getattr(bound, render)())
    result['str'] = str(SnapshotForm(initial={'name': 'x'}))
    formset = SnapshotFormSet(prefix='fs')
    result['formset_as_horizontal'] = str(formset.as_horizontal())
    result['formset_empty_form'] = str(formset.empty_form.as_horizontal())
    return result
