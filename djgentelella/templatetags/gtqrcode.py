"""``{% qrcode value %}``: a value shown as a QR code (``QRCodeView`` in
base.js, the same drawing as ``QRCodeInput``), for detail pages and lists."""

from django import template
from django.utils.html import format_html

from djgentelella.assets import versioned_static

register = template.Library()


@register.simple_tag
def qrcode(value, size=120):
    return format_html(
        '<canvas class="gt-qrcode" data-widget="QRCodeView" data-value="{}" '
        'data-size="{}" data-qr-lib="{}" role="img" aria-label="{}"></canvas>',
        '' if value is None else value, int(size),
        versioned_static('vendors/qrcode/qrcode.js'), '' if value is None else value)
