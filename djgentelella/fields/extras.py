"""Form fields that validate on the server what the widgets of
:mod:`djgentelella.widgets.extras` draw in the browser."""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from djgentelella.widgets.extras import RangePairInput, StarRatingInput


class RatingField(forms.IntegerField):
    """An integer from 0 to ``stars`` (``StarRatingInput``). Empty is
    ``None``, or 0 with ``empty_value=0``."""

    def __init__(self, *, stars=5, readonly=False, empty_value=None, **kwargs):
        self.stars = int(stars)
        self.empty_value = empty_value
        kwargs.setdefault('widget', StarRatingInput(stars=self.stars,
                                                    readonly=readonly))
        kwargs['min_value'] = 0
        kwargs['max_value'] = self.stars
        super().__init__(**kwargs)

    def clean(self, value):
        # After validation: a required field must not take 0 for empty.
        value = super().clean(value)
        return self.empty_value if value is None else value


class RangePairField(forms.MultiValueField):
    """A ``(low, high)`` pair within ``min_value``..``max_value``
    (``RangePairInput``), where ``low <= high``.

    The values are integers, or decimals when ``decimal_places`` is given.
    """

    default_error_messages = {
        'order': _('The minimum cannot be greater than the maximum.'),
    }

    def __init__(self, *, min_value, max_value, step=None, decimal_places=None,
                 suffix='', **kwargs):
        if decimal_places is None:
            def make():
                return forms.IntegerField(min_value=min_value, max_value=max_value)
        else:
            def make():
                return forms.DecimalField(min_value=min_value, max_value=max_value,
                                          decimal_places=decimal_places)
        if step is None and decimal_places is not None:
            step = '0.' + '0' * (decimal_places - 1) + '1' if decimal_places else 1
        kwargs.setdefault('widget', RangePairInput(
            min_value=min_value, max_value=max_value, step=step, suffix=suffix))
        super().__init__(fields=(make(), make()), require_all_fields=True,
                         **kwargs)

    def compress(self, data_list):
        if not data_list or all(value is None for value in data_list):
            return None
        low, high = data_list
        if low is not None and high is not None and low > high:
            raise ValidationError(self.error_messages['order'], code='order')
        return (low, high)
