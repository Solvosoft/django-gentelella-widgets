from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from djgentelella.geocoding import geocoder_configured

from .core import TextInput, js_widget_name, update_kwargs


class GeocodedAddressInput(TextInput):
    """An address, and the button that finds it on the map.

    The text is the value of the field. With a geocoder configured
    (``GT_GEOCODER``, off by default: see :mod:`djgentelella.geocoding`) a
    search button lists the places that match it; choosing one writes its
    ``"lat,lng"`` into the field ``point_field`` of the same form -- usually a
    ``GTPointField`` with ``MapPointInput``, whose marker moves -- and, with
    ``replace_text=True``, the address the geocoder found into this one.
    Without a geocoder it is a plain text input.
    """

    template_name = 'gentelella/widgets/geocoded_address.html'

    def __init__(self, attrs=None, point_field=None, replace_text=False,
                 extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self))
        attrs = attrs or {}
        if point_field:
            attrs['data-point-field'] = point_field
        if replace_text:
            attrs['data-replace-text'] = 'true'
        self.point_field = point_field
        super().__init__(attrs, extraskwargs=False)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        # A widget has no request: a function of the request may still find
        # no geocoder for one, and the endpoint then answers 404.
        enabled = geocoder_configured()
        if enabled:
            context['widget']['attrs']['data-geocode-url'] = reverse('gt-geocode')
        context['geocoder'] = enabled
        context['texts'] = {'search': _('Find on the map'),
                            'empty': _('No places found')}
        return context
