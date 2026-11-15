from decimal import Decimal, InvalidOperation

from django import forms
from django.core.exceptions import ValidationError
from django.forms import formset_factory
from django.utils.translation import gettext_lazy as _

from demoapp.models import DynamicContact
from djgentelella.fields.lov import LOVChoiceField
from djgentelella.forms.dynamic import When
from djgentelella.forms.forms import GTForm, GTFormSet
from djgentelella.widgets import core as genwidgets


# The total column holds 14 digits, two of them decimals.
MAX_TOTAL = Decimal('1e12')


def _decimal(value):
    """The browser sends anything: NaN, Infinity and garbage count as 0."""
    try:
        number = Decimal(str(value).replace(',', '.'))
    except (InvalidOperation, ValueError):
        return Decimal(0)
    return number if number.is_finite() else Decimal(0)


class DynamicContactForm(GTForm, forms.ModelForm):
    country = LOVChoiceField('demo_countries', label=_('Country'))
    province = LOVChoiceField('demo_provinces', label=_('Province'), required=False)
    canton = LOVChoiceField('demo_cantons', label=_('Canton'), required=False)
    # Not stored: a checkbox for the is_checked() condition.
    send_copy = forms.BooleanField(label=_('Send me a copy'), required=False,
                                   widget=genwidgets.CheckboxInput)
    copy_email = forms.EmailField(label=_('Copy to'), required=False,
                                  widget=genwidgets.EmailInput)

    dynamic_actions = [
        When('kind').equals('company').show('company_name', 'company_id')
        .require('company_id'),
        When('quantity', 'price', 'discount').changes()
        .set_value('total', server='calc_total'),
        When('discount').gt(50).confirm(_('Discount greater than 50%?')),
        When('discount').gt(30).add_class('is-invalid', 'discount'),
        When('send_copy').is_checked().show('copy_email').require('copy_email'),
    ]

    def calc_total(self, data):
        """Runs on the server: ``data`` is the raw form data, unprefixed."""
        quantity = _decimal(data.get('quantity'))
        price = _decimal(data.get('price'))
        discount = min(max(_decimal(data.get('discount')), Decimal(0)), Decimal(100))
        total = quantity * price * (1 - discount / 100)
        if abs(total) >= MAX_TOTAL:
            # quantize() of 1e999999 raises InvalidOperation: answer a 400.
            raise ValidationError(_('The total is too large.'))
        return {'total': str(total.quantize(Decimal('0.01')))}

    def clean(self):
        cleaned = super().clean()
        # The browser only asks for it; the server has to check it as well.
        if cleaned.get('kind') == 'company' and not cleaned.get('company_id'):
            self.add_error('company_id', _('A company needs its id.'))
        if cleaned.get('send_copy') and not cleaned.get('copy_email'):
            self.add_error('copy_email', _('Where should the copy go?'))
        return cleaned

    class Meta:
        model = DynamicContact
        fields = ['kind', 'name', 'company_name', 'company_id', 'country',
                  'province', 'canton', 'quantity', 'price', 'discount', 'total']
        widgets = {
            'kind': genwidgets.Select,
            'name': genwidgets.TextInput,
            'company_name': genwidgets.TextInput,
            'company_id': genwidgets.TextInput,
            'quantity': genwidgets.NumberInput,
            'price': genwidgets.NumberInput,
            'discount': genwidgets.NumberInput,
            'total': genwidgets.NumberInput(attrs={'readonly': True}),
        }


DynamicContactFormSet = formset_factory(DynamicContactForm, formset=GTFormSet,
                                        extra=1, can_delete=True)
