from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from djgentelella.widgets.maps import MapPointInput

#: Room for "-12.345678,-123.456789" plus a little slack.
DEFAULT_MAX_LENGTH = 63


def parse_point(value):
    """``"lat,lng"`` -> ``(lat, lng)`` floats, or ``None`` when unparseable.

    Deliberately strict, so a malformed value is reported instead of being
    coerced into a plausible-looking point somewhere else on the planet.
    """
    if value in (None, ""):
        return None
    parts = str(value).strip().split(",")
    if len(parts) != 2:
        return None
    try:
        lat = float(parts[0])
        lng = float(parts[1])
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return None
    return lat, lng


def validate_latlng(value):
    """Validator with one message per failure mode, not a single generic one."""
    if value in (None, ""):
        return
    parts = str(value).strip().split(",")
    if len(parts) != 2:
        raise ValidationError(
            _("Enter a point as 'latitude,longitude'."), code="invalid_format"
        )
    try:
        lat = float(parts[0])
        lng = float(parts[1])
    except (TypeError, ValueError):
        raise ValidationError(
            _("Latitude and longitude must be numbers."), code="invalid_number"
        )
    if not (-90 <= lat <= 90):
        raise ValidationError(
            _("Latitude must be between -90 and 90."), code="invalid_latitude"
        )
    if not (-180 <= lng <= 180):
        raise ValidationError(
            _("Longitude must be between -180 and 180."), code="invalid_longitude"
        )


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
        parts = [part.strip() for part in value.split(",")]
        return ",".join(parts)


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
        kwargs.setdefault("max_length", DEFAULT_MAX_LENGTH)
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
        if kwargs.get("max_length") == DEFAULT_MAX_LENGTH:
            del kwargs["max_length"]
        if self.zoom is not None:
            kwargs["zoom"] = self.zoom
        if self.center is not None:
            kwargs["center"] = self.center
        if self.based_fields is not None:
            kwargs["based_fields"] = self.based_fields
        if self.search:
            kwargs["search"] = self.search
        if self.map_attrs is not None:
            kwargs["map_attrs"] = self.map_attrs
        return name, path, args, kwargs

    def formfield(self, **kwargs):
        widget_kwargs = {
            "zoom": self.zoom,
            "center": self.center,
            "based_fields": self.based_fields,
            "search": self.search,
        }
        if self.map_attrs:
            widget_kwargs["attrs"] = self.map_attrs
        defaults = {
            "form_class": GTPointFormField,
            "widget": MapPointInput(**widget_kwargs),
        }
        defaults.update(kwargs)
        # CharField.formfield insists on passing max_length to the form field,
        # which GTPointFormField accepts, so nothing else has to be stripped.
        return super().formfield(**defaults)
