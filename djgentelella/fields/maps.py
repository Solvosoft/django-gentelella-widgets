from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from djgentelella.widgets.maps import MapPointInput

#: Room for "-12.345678,-123.456789" plus a little slack.
DEFAULT_MAX_LENGTH = 63


#: One message per failure mode, keyed by the ValidationError code
#: ``validate_latlng`` raises.
LATLNG_ERRORS = {
    'invalid_format': _("Enter a point as 'latitude,longitude'."),
    'invalid_number': _('Latitude and longitude must be numbers.'),
    'invalid_latitude': _('Latitude must be between -90 and 90.'),
    'invalid_longitude': _('Longitude must be between -180 and 180.'),
}


def _read_latlng(value):
    """``"lat,lng"`` -> ``(error_code, point)``, exactly one of them None.

    The single place that knows how a point is spelled. ``parse_point`` only
    needs the point and ``validate_latlng`` only needs the code, but both used
    to reimplement the same split/float/range walk, so a fix to one silently
    skipped the other.
    """
    parts = str(value).strip().split(',')
    if len(parts) != 2:
        return 'invalid_format', None
    try:
        lat = float(parts[0])
        lng = float(parts[1])
    except (TypeError, ValueError):
        return 'invalid_number', None
    if not (-90 <= lat <= 90):
        return 'invalid_latitude', None
    if not (-180 <= lng <= 180):
        return 'invalid_longitude', None
    return None, (lat, lng)


def parse_point(value):
    """``"lat,lng"`` -> ``(lat, lng)`` floats, or ``None`` when unparseable.

    Deliberately strict, so a malformed value is reported instead of being
    coerced into a plausible-looking point somewhere else on the planet.
    """
    if value in (None, ''):
        return None
    return _read_latlng(value)[1]


def validate_latlng(value):
    """Validator with one message per failure mode, not a single generic one."""
    if value in (None, ''):
        return
    code = _read_latlng(value)[0]
    if code is not None:
        raise ValidationError(LATLNG_ERRORS[code], code=code)


class GTPointFormField(forms.CharField):
    """Form field for a ``"lat,lng"`` point, rendered with a Leaflet map."""

    widget = MapPointInput
    default_validators = [validate_latlng]

    def to_python(self, value):
        value = super().to_python(value)
        if not value:
            return value
        # Normalize so "9.9327 , -84.0875" and "9.9327,-84.0875" store the same
        # string and comparisons between a saved and a submitted value hold.
        parts = [part.strip() for part in value.split(',')]
        return ','.join(parts)


class GTPointField(models.CharField):
    """Model field storing a GPS point as the string ``"lat,lng"``.

    A plain ``CharField``, so no GeoDjango, GDAL or PostGIS is needed and it
    works on SQLite. Use ``parse_point(obj.location)`` to get numbers back.

    The map options (``zoom``, ``center``, ``based_fields``...) are forwarded to
    :class:`~djgentelella.widgets.maps.MapPointInput` by ``formfield()``.
    """

    description = _("GPS point stored as 'latitude,longitude'")
    default_validators = [validate_latlng]

    def __init__(self, *args, zoom=None, center=None, based_fields=None,
                 search=False, map_attrs=None, **kwargs):
        kwargs.setdefault('max_length', DEFAULT_MAX_LENGTH)
        self.zoom = zoom
        self.center = center
        self.based_fields = based_fields
        self.search = search
        self.map_attrs = map_attrs
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        """Re-emit the extra kwargs so migrations round-trip.

        django-location-field omits this, which makes its model fields
        undeconstructible; ``makemigrations --check`` (run by ``make sdist``)
        would catch that here.
        """
        name, path, args, kwargs = super().deconstruct()
        if kwargs.get('max_length') == DEFAULT_MAX_LENGTH:
            del kwargs['max_length']
        if self.zoom is not None:
            kwargs['zoom'] = self.zoom
        if self.center is not None:
            kwargs['center'] = self.center
        if self.based_fields is not None:
            kwargs['based_fields'] = self.based_fields
        if self.search:
            kwargs['search'] = self.search
        if self.map_attrs is not None:
            kwargs['map_attrs'] = self.map_attrs
        return name, path, args, kwargs

    def formfield(self, **kwargs):
        widget_kwargs = {
            'zoom': self.zoom,
            'center': self.center,
            'based_fields': self.based_fields,
            'search': self.search,
        }
        if self.map_attrs:
            widget_kwargs['attrs'] = self.map_attrs
        defaults = {
            'form_class': GTPointFormField,
            'widget': MapPointInput(**widget_kwargs),
        }
        defaults.update(kwargs)
        # CharField.formfield insists on passing max_length to the form field,
        # which GTPointFormField accepts, so nothing else has to be stripped.
        return super().formfield(**defaults)
