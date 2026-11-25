from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.template.defaultfilters import filesizeformat
from django.utils.translation import gettext_lazy as _

from djgentelella.widgets.imagecrop import ImageCropInput

#: Formats of Pillow accepted by default: the ones every browser shows.
DEFAULT_FORMATS = ('JPEG', 'PNG', 'WEBP', 'GIF')


def default_max_size():
    """``GT_IMAGE_MAX_SIZE``, in bytes (5 MB by default)."""
    return getattr(settings, 'GT_IMAGE_MAX_SIZE', 5 * 1024 * 1024)


class ImageCropField(forms.ImageField):
    """An image checked on the server whatever the browser did.

    Django's ``ImageField`` already opens the file with Pillow and rejects
    what is not an image. This adds the formats (``formats``, Pillow names)
    and the size (``max_size`` bytes, ``GT_IMAGE_MAX_SIZE`` by default).
    """

    default_error_messages = {
        'format': _('Images in %(format)s are not accepted. Use %(formats)s.'),
        'size': _('The image is %(size)s; the limit is %(max)s.'),
    }

    def __init__(self, *, formats=DEFAULT_FORMATS, max_size=None, aspect_ratio=None,
                 max_width=None, max_height=None, **kwargs):
        self.formats = tuple(name.upper() for name in formats)
        self.max_size = default_max_size() if max_size is None else max_size
        kwargs.setdefault('widget', ImageCropInput(
            aspect_ratio=aspect_ratio, max_width=max_width, max_height=max_height))
        super().__init__(**kwargs)

    def to_python(self, data):
        if data in self.empty_values:
            return None
        if self.max_size and getattr(data, 'size', 0) > self.max_size:
            raise ValidationError(
                self.error_messages['size'], code='size',
                params={'size': filesizeformat(data.size),
                        'max': filesizeformat(self.max_size)})
        image = super().to_python(data)
        found = getattr(getattr(image, 'image', None), 'format', None)
        if found and self.formats and found.upper() not in self.formats:
            raise ValidationError(
                self.error_messages['format'], code='format',
                params={'format': found, 'formats': ', '.join(self.formats)})
        return image
