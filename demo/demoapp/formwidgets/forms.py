from django import forms

from djgentelella.fields.extras import RangePairField, RatingField
from djgentelella.fields.imagecrop import ImageCropField
from djgentelella.fields.lov import LOVChoiceField
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as genwidgets
from djgentelella.widgets.extras import ComboboxInput, QRCodeInput, RangeInput, \
    SwitchInput
from djgentelella.widgets.geocoding import GeocodedAddressInput
from djgentelella.widgets.lov import LOVPopupSelect
from djgentelella.widgets.maps import MapPointInput
from djgentelella.widgets.markdown import MarkdownInput

from demoapp.models import WidgetShowcase

CATEGORIES = ['Hardware', 'Software', 'Services', 'Training']


class WidgetShowcaseForm(GTForm, forms.ModelForm):
    """One field per widget of the catalog (2.1)."""

    rating = RatingField(stars=5, required=False, empty_value=0, label='Rating')
    budget = RangePairField(min_value=0, max_value=1000, step=50, required=False,
                            suffix=' $', label='Budget')
    product = LOVChoiceField('demo_products', widget=LOVPopupSelect,
                             required=False, label='Product')
    photo = ImageCropField(required=False, aspect_ratio=1, max_width=800,
                           max_height=800, label='Photo')

    grid_representation = [
        [['name'], ['category']],
        [['rating'], ['active'], ['volume']],
        [['budget'], ['product']],
        [['description']],
        [['photo'], ['code']],
        [['address']],
        [['location']],
    ]

    class Meta:
        model = WidgetShowcase
        fields = ['name', 'rating', 'active', 'volume', 'category', 'product',
                  'description', 'photo', 'code', 'address', 'location']
        widgets = {
            'name': genwidgets.TextInput,
            'active': SwitchInput(label='Enabled'),
            'volume': RangeInput(min_value=0, max_value=100, suffix=' %'),
            'category': ComboboxInput(choices=CATEGORIES),
            'description': MarkdownInput,
            'code': QRCodeInput(scan=True),
            'address': GeocodedAddressInput(point_field='location'),
            'location': MapPointInput(zoom=8, center=(9.9327, -84.0875)),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.budget_min is not None:
            self.initial['budget'] = (self.instance.budget_min,
                                      self.instance.budget_max)

    def save(self, commit=True):
        budget = self.cleaned_data.get('budget') or (None, None)
        self.instance.budget_min, self.instance.budget_max = budget
        return super().save(commit=commit)
