from django.forms import ClearableFileInput as DJClearableFileInput
from django.templatetags.static import static
from django.utils.translation import gettext_lazy as _

from .core import js_widget_name, update_kwargs


class ImageCropInput(DJClearableFileInput):
    """An image upload cropped in the browser before it is sent.

    When a file is chosen, Cropper.js shows it with a crop box of
    ``aspect_ratio`` (``16 / 9``, ``1``; None is free); "Apply" replaces the
    file of the input with the cropped image, at most ``max_width`` x
    ``max_height`` pixels, encoded as ``output_type``. It is still a normal
    ``<input type="file">``: the form posts multipart, an edit form shows the
    current image and can clear an optional one, and without javascript the
    file goes as chosen.

    The browser can be skipped, so the server checks again: use it with
    :class:`~djgentelella.fields.imagecrop.ImageCropField` (type, format and
    size), or at least with Django's ``ImageField``.
    """

    template_name = 'gentelella/widgets/image_crop.html'

    def __init__(self, attrs=None, aspect_ratio=None, max_width=None,
                 max_height=None, output_type='image/jpeg', quality=0.9,
                 extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self))
        attrs = attrs or {}
        attrs.setdefault('accept', 'image/*')
        if aspect_ratio is not None:
            attrs['data-aspect-ratio'] = float(aspect_ratio)
        if max_width is not None:
            attrs['data-max-width'] = int(max_width)
        if max_height is not None:
            attrs['data-max-height'] = int(max_height)
        attrs['data-output-type'] = output_type
        attrs['data-quality'] = quality
        super().__init__(attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        widget_attrs = context['widget']['attrs']
        widget_attrs['data-cropper-js'] = static('vendors/cropperjs/cropper.min.js')
        widget_attrs['data-cropper-css'] = static('vendors/cropperjs/cropper.min.css')
        context['texts'] = {
            'apply': _('Apply crop'), 'cancel': _('Cancel'),
            'rotate': _('Rotate'), 'reset': _('Reset'),
            'current': _('Current image'), 'new': _('New image'),
        }
        return context
