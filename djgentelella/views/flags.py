"""Serve flags out of the committed sprite, one at a time or all at once.

Replaces ``djgentelella.flags.vendors.min.css``, a 6.35 MB stylesheet that
base64-inlined all 266 flags and had to be downloaded in full to show one.
"""
import gzip
import hashlib

from django.http import Http404, HttpResponse
from django.utils.html import escape
from django.views import View

from djgentelella.flags import get_index, get_sprite_bytes

SVG_CONTENT_TYPE = 'image/svg+xml'
# Flags do not change between releases, and flag_url() puts the package version
# in the query string, so an upgraded sprite is picked up despite this.
CACHE_CONTROL = 'public, max-age=31536000, immutable'

SHAPES = ('circle', 'rounded')
MAX_SIZE = 2048


def _cache(response, payload):
    response['Cache-Control'] = CACHE_CONTROL
    response['ETag'] = '"%s"' % hashlib.sha256(payload).hexdigest()[:32]
    return response


def _square_viewbox(viewbox):
    """The centred square of a viewBox, so a shaped flag comes out square.

    Cropping through the viewBox rather than ``preserveAspectRatio`` keeps the
    clip path's coordinates and the visible area in the same system, which is
    what lets the circle below be the inscribed one whatever the source ratio.
    """
    min_x, min_y, width, height = (float(n) for n in viewbox.split())
    side = min(width, height)
    return (min_x + (width - side) / 2, min_y + (height - side) / 2, side)


def _clip(shape, code, viewbox):
    """``(defs, group_attr)`` clipping a flag to a circle or a rounded square."""
    x, y, side = _square_viewbox(viewbox)
    clip_id = 'gtclip-%s-%s' % (code, shape)
    if shape == 'circle':
        figure = '<circle cx="%g" cy="%g" r="%g"/>' % (
            x + side / 2, y + side / 2, side / 2)
    else:
        figure = '<rect x="%g" y="%g" width="%g" height="%g" rx="%g"/>' % (
            x, y, side, side, side / 8)
    return ('<defs><clipPath id="%s">%s</clipPath></defs>' % (clip_id, figure),
            ' clip-path="url(#%s)"' % clip_id)


class FlagIconView(View):
    """One flag as a standalone SVG: ``/flags/cr.svg``.

    Query parameters, all optional:

    ``size``
        Width in pixels; the height follows the flag's own ratio, or matches
        ``size`` when a shape is given.
    ``shape``
        ``circle`` or ``rounded`` -- crops the flag to the centred square and
        clips it. Anything else is ignored.
    ``title``
        Accessible name, emitted as a ``<title>`` child.

    With none of them the symbol body is returned untouched.
    """

    def get_size(self, request):
        try:
            size = int(request.GET.get('size', ''))
        except ValueError:
            return None
        # A negative or absurd size would only ever be a mistake, and clamping
        # keeps the generated markup valid.
        return max(1, min(size, MAX_SIZE))

    def get(self, request, code):
        index = get_index()
        if code not in index:
            # No fallback to the `xx` placeholder: it would turn a typo into a
            # blank flag that renders fine and is never noticed.
            raise Http404('unknown flag %r' % code)

        viewbox, body = index[code]
        shape = request.GET.get('shape')
        shape = shape if shape in SHAPES else None
        size = self.get_size(request)
        defs = ''

        if shape:
            x, y, side = _square_viewbox(viewbox)
            defs, clip_attr = _clip(shape, code, viewbox)
            viewbox = '%g %g %g %g' % (x, y, side, side)
            body = '<g%s>%s</g>' % (clip_attr, body)

        attrs = ['xmlns="http://www.w3.org/2000/svg"',
                 'xmlns:xlink="http://www.w3.org/1999/xlink"',
                 'viewBox="%s"' % viewbox]
        if size:
            min_x, min_y, width, height = (float(n) for n in viewbox.split())
            attrs.append('width="%d"' % size)
            attrs.append('height="%d"' % max(1, round(size * height / width)))

        title = request.GET.get('title')
        head = '<title>%s</title>' % escape(title) if title else ''

        payload = ('<svg %s>%s%s%s</svg>' % (
            ' '.join(attrs), head, defs, body)).encode('utf-8')
        return _cache(HttpResponse(payload, content_type=SVG_CONTENT_TYPE),
                      payload)


class FlagSpriteView(View):
    """The whole sprite, for ``<use href="…/flags/sprite.svg#fi-cr">``.

    Handed to the browser still gzipped -- it is committed that way, so there is
    nothing to compress at request time. ``GZipMiddleware`` leaves a response
    that already declares a ``Content-Encoding`` alone, so this cannot end up
    doubly compressed.
    """

    def get(self, request):
        payload = get_sprite_bytes()
        accepted = request.META.get('HTTP_ACCEPT_ENCODING', '')
        if 'gzip' in accepted.lower():
            response = HttpResponse(payload, content_type=SVG_CONTENT_TYPE)
            response['Content-Encoding'] = 'gzip'
            return _cache(response, payload)

        plain = gzip.decompress(payload)
        return _cache(HttpResponse(plain, content_type=SVG_CONTENT_TYPE), plain)
