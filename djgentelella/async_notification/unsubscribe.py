"""
One-click unsubscribe support (RFC 8058 / RFC 2369).

Builds signed per-recipient unsubscribe tokens, absolute HTTPS URLs, and the
``List-Unsubscribe`` / ``List-Unsubscribe-Post`` headers that let mailbox
providers (Gmail, Yahoo, ...) show a native unsubscribe button.
"""

from django.core import signing
from django.urls import reverse

from djgentelella.async_notification.settings import (
    ASYNC_NOTIFICATION_BASE_URL,
    ASYNC_NOTIFICATION_UNSUBSCRIBE_MAILTO,
    ASYNC_NOTIFICATION_UNSUBSCRIBE_MAX_AGE,
)

SALT = 'async_notification.unsubscribe'


def make_token(email):
    """Return a signed, URL-safe token identifying ``email``."""
    return signing.dumps(email, salt=SALT)


def read_token(token):
    """Return the email encoded in ``token``.

    Raises ``signing.BadSignature`` (or ``SignatureExpired``) if invalid.
    """
    kwargs = {'salt': SALT}
    if ASYNC_NOTIFICATION_UNSUBSCRIBE_MAX_AGE:
        kwargs['max_age'] = ASYNC_NOTIFICATION_UNSUBSCRIBE_MAX_AGE
    return signing.loads(token, **kwargs)


def _base_url():
    if ASYNC_NOTIFICATION_BASE_URL:
        return ASYNC_NOTIFICATION_BASE_URL.rstrip('/')
    try:
        # django.contrib.sites is optional; a project without it falls back
        # to the empty base URL below.
        from django.contrib.sites.models import Site  # noqa: PLC0415
        return f'https://{Site.objects.get_current().domain}'
    except Exception:
        return ''


def unsubscribe_url(email):
    """Absolute HTTPS one-click unsubscribe URL, or '' if no base URL known."""
    base = _base_url()
    if not base:
        return ''
    return base + reverse(
        'async_notification:unsubscribe', args=[make_token(email)])


def unsubscribe_headers(email):
    """Return (headers dict, https_url) for a single recipient.

    ``headers`` carries ``List-Unsubscribe`` (HTTPS and/or mailto) plus
    ``List-Unsubscribe-Post`` when a one-click HTTPS URL is available.
    """
    url = unsubscribe_url(email)
    targets = []
    if url:
        targets.append(f'<{url}>')
    if ASYNC_NOTIFICATION_UNSUBSCRIBE_MAILTO:
        targets.append(
            f'<mailto:{ASYNC_NOTIFICATION_UNSUBSCRIBE_MAILTO}'
            f'?subject=unsubscribe>')
    headers = {}
    if targets:
        headers['List-Unsubscribe'] = ', '.join(targets)
        if url:
            headers['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'
    return headers, url
