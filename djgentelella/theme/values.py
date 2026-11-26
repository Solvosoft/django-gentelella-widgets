"""What a theme may hold, and how each value is checked.

A theme is a handful of typed values -- six colours, a radius, a font out of a
fixed list and a logo -- never CSS: :mod:`djgentelella.theme.css` writes the
stylesheet from them, so nothing a user types reaches it as it is. Every value
is validated twice, by the model field and again when the CSS is written.
"""

import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
from PIL import Image

#: ``#rrggbb``: the only colour syntax a theme accepts.
HEX_PATTERN = r'^#[0-9a-fA-F]{6}$'
HEX_RE = re.compile(HEX_PATTERN)

hex_color = RegexValidator(
    HEX_PATTERN, _('Enter a colour as #rrggbb (six hexadecimal digits).'),
    code='invalid_color')

#: What a colour field takes as typed: ``#rrggbb`` or the short ``#rgb``,
#: which :func:`normalize_color` turns into the first before it is checked.
INPUT_PATTERN = r'^#(?:[0-9a-fA-F]{3}){1,2}$'
SHORT_HEX_RE = re.compile(r'^#([0-9a-fA-F])([0-9a-fA-F])([0-9a-fA-F])$')


def normalize_color(value):
    """``value`` as the theme stores it: ``#rgb`` becomes ``#rrggbb``, the
    digits lower case, the blanks around it gone (``' #ABC '`` ->
    ``'#aabbcc'``). Anything else is returned as it is (stripped, when it is
    a string), for the validator to refuse it."""
    if not isinstance(value, str):
        return value
    value = value.strip()
    short = SHORT_HEX_RE.match(value)
    if short:
        value = '#' + ''.join(digit * 2 for digit in short.groups())
    if HEX_RE.match(value):
        return value.lower()
    return value


#: The colours of a theme: ``field -> label``, in the order of the form.
COLORS = {
    'primary': _('Primary'),
    'secondary': _('Secondary'),
    'success': _('Success'),
    'danger': _('Danger'),
    'sidebar_bg': _('Sidebar background'),
    'sidebar_text': _('Sidebar text'),
}

#: Border radius, in pixels.
RADIUS_MIN, RADIUS_MAX = 0, 24

#: The fonts a theme may choose: ``key -> (label, font stack)``. Only system
#: fonts: a theme downloads nothing.
FONTS = {
    'system': (_('System'), 'system-ui, -apple-system, "Segoe UI", Roboto, '
                            '"Helvetica Neue", Arial, sans-serif'),
    'sans': (_('Sans serif'), '"Helvetica Neue", Helvetica, Arial, sans-serif'),
    'humanist': (_('Humanist'), '"Trebuchet MS", "Lucida Grande", '
                                '"Lucida Sans Unicode", Verdana, sans-serif'),
    'serif': (_('Serif'), 'Georgia, Cambria, "Times New Roman", Times, serif'),
    'mono': (_('Monospace'), 'SFMono-Regular, Menlo, Consolas, '
                             '"Liberation Mono", monospace'),
}
FONT_CHOICES = [(key, label) for key, (label, _stack) in FONTS.items()]

#: The image formats a logo may have: Pillow's name -> (extensions, type).
#: Never SVG: an SVG is a document that can carry scripts.
LOGO_FORMATS = {
    'PNG': (('png',), 'image/png'),
    'JPEG': (('jpg', 'jpeg'), 'image/jpeg'),
    'GIF': (('gif',), 'image/gif'),
    'WEBP': (('webp',), 'image/webp'),
}


def logo_max_bytes():
    """``GT_THEME_LOGO_MAX_BYTES``, 512 KB by default."""
    return int(getattr(settings, 'GT_THEME_LOGO_MAX_BYTES', 512 * 1024))


def logo_content_type(name):
    """The content type a logo is served with, from its (validated)
    extension; ``None`` for any other."""
    extension = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    for extensions, content_type in LOGO_FORMATS.values():
        if extension in extensions:
            return content_type
    return None


def validate_logo(upload):
    """Refuse a logo that is too big, that is not a PNG, JPEG, GIF or WebP
    image, or whose extension says another format than its content."""
    if not upload or getattr(upload, '_committed', False):
        return  # nothing, or the file already stored (validated on upload)
    if upload.size > logo_max_bytes():
        raise ValidationError(
            _('The logo is too big: %(size)d KB at most.')
            % {'size': logo_max_bytes() // 1024}, code='logo_size')
    name = getattr(upload, 'name', '') or ''
    extension = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    position = upload.tell() if hasattr(upload, 'tell') else 0
    try:
        upload.seek(0)
        with Image.open(upload) as image:
            image_format = image.format
            image.verify()
    except Exception:  # Pillow raises many kinds for a broken file
        raise ValidationError(_('The logo is not an image.'), code='logo_invalid')
    finally:
        try:
            upload.seek(position)
        except (AttributeError, ValueError):
            pass
    allowed = LOGO_FORMATS.get(image_format)
    if allowed is None:
        raise ValidationError(_('The logo must be a PNG, JPEG, GIF or WebP image.'),
                              code='logo_format')
    if extension not in allowed[0]:
        raise ValidationError(
            _('The name of the logo does not match its format (%(format)s).')
            % {'format': image_format}, code='logo_extension')
