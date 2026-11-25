"""Push backends: how a payload reaches one subscription.

``GT_PUSH_BACKEND`` names the class (a dotted path); the default,
:class:`WebPushBackend`, sends with ``pywebpush`` (the ``[push]`` extra) and
the VAPID keys of the settings. Without the extra or without the keys it is
not :meth:`~BasePushBackend.available` and push is simply off.

A backend implements :meth:`~BasePushBackend.send`, which raises
:class:`PushGone` when the push service says the subscription no longer
exists (404/410): the caller deletes it. Any other exception is logged and the
subscription is kept.
"""
import base64

from djgentelella.pwa import conf


class PushGone(Exception):
    """The push service no longer knows the subscription (404 or 410)."""


class BasePushBackend:
    """What :func:`djgentelella.pwa.push.send_push` needs from a backend."""

    def available(self):
        """True when this backend can send. False turns push off."""
        return True

    def application_server_key(self):
        """The VAPID public key (base64url, uncompressed P-256 point) the
        browser subscribes with."""
        return conf.vapid_public_key()

    def send(self, subscription, payload):
        """Deliver ``payload`` (a JSON string) to ``subscription``."""
        raise NotImplementedError


class LocmemPushBackend(BasePushBackend):
    """Keeps what it sends in :data:`outbox`, like Django's locmem mail
    backend: for tests and for development without a push service.

    A subscription whose endpoint is in :data:`gone` raises :class:`PushGone`.
    """

    outbox = []
    gone = set()

    def application_server_key(self):
        return conf.vapid_public_key() or base64.urlsafe_b64encode(
            b'\x04' + b'\x01' * 64).rstrip(b'=').decode()

    def send(self, subscription, payload):
        if subscription.endpoint in self.gone:
            raise PushGone(subscription.endpoint)
        self.outbox.append({'endpoint': subscription.endpoint,
                            'subscription': subscription.subscription_info(),
                            'payload': payload})


def _pywebpush():
    """The ``pywebpush`` module, or ``None`` without the ``[push]`` extra."""
    try:
        import pywebpush  # noqa: PLC0415 -- optional dependency, the [push] extra
    except ImportError:
        return None
    return pywebpush


def _vapid(private_key):
    """A ``py_vapid.Vapid`` from the key of the setting: PEM text, or the
    base64url DER/raw form ``vapid --gen`` and ``gt_vapid_keys`` print."""
    from py_vapid import Vapid  # noqa: PLC0415 -- optional dependency, the [push] extra
    key = private_key.strip()
    if key.startswith('-----BEGIN'):
        return Vapid.from_pem(key.encode())
    return Vapid.from_string(private_key=key)


def public_key_of(private_key):
    """The base64url application server key of a VAPID private key."""
    from cryptography.hazmat.primitives import serialization  # noqa: PLC0415 -- optional dependency, the [push] extra
    raw = _vapid(private_key).public_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()


class WebPushBackend(BasePushBackend):
    """Web push with VAPID through ``pywebpush``.

    Needs the ``[push]`` extra and ``GT_PUSH_VAPID_PRIVATE_KEY``;
    ``GT_PUSH_VAPID_PUBLIC_KEY`` is derived from it when not set.
    """

    def __init__(self):
        self._key = None

    def available(self):
        return bool(conf.vapid_private_key()) and _pywebpush() is not None

    def application_server_key(self):
        public = conf.vapid_public_key()
        if public or not self.available():
            return public
        return public_key_of(conf.vapid_private_key())

    def vapid(self):
        if self._key is None:
            self._key = _vapid(conf.vapid_private_key())
        return self._key

    def send(self, subscription, payload):
        pywebpush = _pywebpush()
        try:
            pywebpush.webpush(
                subscription_info=subscription.subscription_info(),
                data=payload,
                vapid_private_key=self.vapid(),
                vapid_claims={'sub': conf.vapid_subject()},
                ttl=conf.push_ttl(),
                timeout=conf.push_timeout(),
            )
        except pywebpush.WebPushException as error:
            if error.status_code in (404, 410):
                raise PushGone(subscription.endpoint) from error
            raise
