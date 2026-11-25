"""The stylesheet of a theme: Bootstrap 5's CSS variables, written from the
validated values of a :class:`~djgentelella.models.SiteTheme`.

Nothing is compiled: Bootstrap reads ``--bs-primary``, ``--bs-border-radius``
and the like at run time, so overriding them after its own stylesheet is
enough. The buttons, the pagination and the checked boxes carry their colour
in variables of their own, which are set here too, with the hover and active
shades derived from the colour. Every value is checked again before it is
written (:data:`~djgentelella.theme.values.HEX_RE`, the radius range, the
font list): a value that is not one of them is left out, never copied.
"""

from djgentelella.theme import values

#: The Bootstrap colours a theme sets.
THEME_COLORS = ('primary', 'secondary', 'success', 'danger')


def valid_color(value):
    return isinstance(value, str) and bool(values.HEX_RE.match(value))


def rgb(color):
    """``#rrggbb`` -> ``(r, g, b)``."""
    return tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))


def to_hex(red, green, blue):
    return '#%02x%02x%02x' % tuple(max(0, min(255, round(part)))
                                   for part in (red, green, blue))


def shade(color, factor):
    """``color`` darker (``factor`` < 1) or towards white (> 1)."""
    red, green, blue = rgb(color)
    if factor <= 1:
        return to_hex(red * factor, green * factor, blue * factor)
    mix = factor - 1
    return to_hex(red + (255 - red) * mix, green + (255 - green) * mix,
                  blue + (255 - blue) * mix)


def contrast(color):
    """Black or white, whichever reads better on ``color`` (WCAG relative
    luminance)."""
    def channel(value):
        value /= 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
    red, green, blue = (channel(part) for part in rgb(color))
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return '#000000' if luminance > 0.4 else '#ffffff'


def _rule(selector, declarations):
    if not declarations:
        return ''
    return '%s{%s}\n' % (selector, ';'.join('%s:%s' % item for item in declarations))


def _button(name, color):
    hover, active = shade(color, 0.85), shade(color, 0.75)
    text = contrast(color)
    solid = [('--bs-btn-color', text), ('--bs-btn-bg', color),
             ('--bs-btn-border-color', color),
             ('--bs-btn-hover-color', contrast(hover)),
             ('--bs-btn-hover-bg', hover), ('--bs-btn-hover-border-color', hover),
             ('--bs-btn-active-color', contrast(active)),
             ('--bs-btn-active-bg', active), ('--bs-btn-active-border-color', active),
             ('--bs-btn-disabled-color', text), ('--bs-btn-disabled-bg', color),
             ('--bs-btn-disabled-border-color', color)]
    outline = [('--bs-btn-color', color), ('--bs-btn-border-color', color),
               ('--bs-btn-hover-color', text), ('--bs-btn-hover-bg', color),
               ('--bs-btn-hover-border-color', color),
               ('--bs-btn-active-color', text), ('--bs-btn-active-bg', color),
               ('--bs-btn-active-border-color', color),
               ('--bs-btn-disabled-color', color)]
    return (_rule('.btn-%s' % name, solid)
            + _rule('.btn-outline-%s' % name, outline))


def theme_values(theme):
    """``{field: value}`` of ``theme`` (a model instance or a dict) that are
    valid: the colours, ``border_radius`` and ``font``."""
    get = theme.get if isinstance(theme, dict) else (
        lambda name, default=None: getattr(theme, name, default))
    found = {}
    for name in values.COLORS:
        value = get(name, '')
        if valid_color(value):
            found[name] = value.lower()
    radius = get('border_radius', None)
    if isinstance(radius, int) and not isinstance(radius, bool) and \
            values.RADIUS_MIN <= radius <= values.RADIUS_MAX:
        found['border_radius'] = radius
    font = get('font', '')
    if font in values.FONTS:
        found['font'] = font
    return found


def render_css(theme):
    """The CSS of ``theme``: ``''`` when it sets nothing."""
    found = theme_values(theme)
    root = []
    for name in THEME_COLORS:
        color = found.get(name)
        if color is None:
            continue
        root += [('--bs-%s' % name, color),
                 ('--bs-%s-rgb' % name, '%d,%d,%d' % rgb(color)),
                 ('--bs-%s-text-emphasis' % name, shade(color, 0.4)),
                 ('--bs-%s-bg-subtle' % name, shade(color, 1.8)),
                 ('--bs-%s-border-subtle' % name, shade(color, 1.6))]
    if 'primary' in found:
        primary = found['primary']
        root += [('--bs-link-color', primary),
                 ('--bs-link-color-rgb', '%d,%d,%d' % rgb(primary)),
                 ('--bs-link-hover-color', shade(primary, 0.8)),
                 ('--bs-link-hover-color-rgb', '%d,%d,%d' % rgb(shade(primary, 0.8)))]
    if 'border_radius' in found:
        radius = found['border_radius']
        root += [('--bs-border-radius', '%dpx' % radius),
                 ('--bs-border-radius-sm', '%dpx' % (radius * 3 // 4)),
                 ('--bs-border-radius-lg', '%dpx' % (radius * 4 // 3)),
                 ('--bs-border-radius-xl', '%dpx' % (radius * 2)),
                 ('--bs-border-radius-pill', '50rem')]
    if 'font' in found:
        root.append(('--bs-body-font-family', values.FONTS[found['font']][1]))
    parts = [_rule(':root,[data-bs-theme=light],[data-bs-theme=dark]', root)]
    if 'font' in found:
        parts.append(_rule('body', [('font-family', 'var(--bs-body-font-family)')]))
    for name in THEME_COLORS:
        if name in found:
            parts.append(_button(name, found[name]))
    if 'primary' in found:
        primary = found['primary']
        parts.append(_rule('.nav-pills', [('--bs-nav-pills-link-active-bg', primary)]))
        parts.append(_rule('.pagination', [
            ('--bs-pagination-active-bg', primary),
            ('--bs-pagination-active-border-color', primary)]))
        parts.append(_rule('.form-check-input:checked', [
            ('background-color', primary), ('border-color', primary)]))
    background, text = found.get('sidebar_bg'), found.get('sidebar_text')
    if background:
        parts.append(_rule('body.nav-md,body.nav-sm,.left_col,.left_col .nav_title,'
                           '.left_col .sidebar-footer', [('background', background)]))
    if text:
        parts.append(_rule('.left_col .site_title,.left_col .nav.side-menu>li>a,'
                           '.left_col .nav.child_menu li a,.left_col .menu_section h3,'
                           '.left_col .sidebar-footer a', [
                               ('color', '%s !important' % text)]))
    return ''.join(parts)
