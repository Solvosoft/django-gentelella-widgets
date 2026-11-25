"""Print a new pair of VAPID keys for web push (djgentelella.pwa).

The keys are printed, never stored: put them in the settings (from the
environment, not in the repository).
"""
import base64

from django.core.management import BaseCommand, CommandError

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
except ImportError:                       # without the [push] extra
    ec = serialization = None


def _b64url(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()


def generate_vapid_keys():
    """``(private, public)``: the raw P-256 private number and the
    uncompressed public point, both base64url."""
    if ec is None:
        raise CommandError(
            'cryptography is missing: pip install djgentelella[push]')
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_numbers().private_value.to_bytes(32, 'big')
    public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return _b64url(private), _b64url(public)


class Command(BaseCommand):
    help = 'Print a new VAPID key pair for GT_PUSH_VAPID_PRIVATE_KEY / PUBLIC_KEY.'

    def handle(self, *args, **options):
        private, public = generate_vapid_keys()
        self.stdout.write("GT_PUSH_VAPID_PRIVATE_KEY = '%s'" % private)
        self.stdout.write("GT_PUSH_VAPID_PUBLIC_KEY = '%s'" % public)
