from django import forms
from django.utils.translation import gettext_lazy as _

from djgentelella.forms.forms import GTForm
from djgentelella.models import SiteTheme
from djgentelella.theme import values
from djgentelella.widgets import core as genwidgets


def color_widget():
    # Text, not <input type=color>: a colour input cannot be empty, and an
    # empty value is how a theme keeps the bundled colour. The roller page
    # puts a colour picker next to it.
    return genwidgets.TextInput(attrs={
        'class': 'gt-theme-color', 'placeholder': '#rrggbb', 'maxlength': 7,
        'pattern': values.HEX_PATTERN.strip('^$'), 'autocomplete': 'off'})


class SiteThemeForm(GTForm, forms.ModelForm):
    clear_logo = forms.BooleanField(label=_('Remove the logo'), required=False,
                                    widget=genwidgets.CheckboxInput)

    class Meta:
        model = SiteTheme
        fields = list(values.COLORS) + ['border_radius', 'font', 'logo']
        widgets = {
            **{name: color_widget() for name in values.COLORS},
            'border_radius': genwidgets.NumberInput(attrs={
                'min': values.RADIUS_MIN, 'max': values.RADIUS_MAX}),
            'font': genwidgets.Select,
            'logo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/png,image/jpeg,image/gif,image/webp'}),
        }

    def save(self, commit=True):
        theme = super().save(commit=False)
        if self.cleaned_data.get('clear_logo') and not self.files.get('logo'):
            theme.logo = ''
        if commit:
            theme.save()
        return theme
