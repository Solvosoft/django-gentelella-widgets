"""AES-encrypted model fields.

The key is ``GT_ENCRYPTION_KEY`` when it is set: the base64 of 16, 24 or 32
random bytes (:func:`create_key` makes one), or a list of them, the first one
encrypting and every one decrypting (key rotation). Without it the key is the
first 16 bytes of ``SECRET_KEY``, as before 0.8: a weak key (a few printable
characters of a secret meant for signing) that changes whenever
``SECRET_KEY`` is rotated. That legacy key always stays a decryption key, so
values written before ``GT_ENCRYPTION_KEY`` was set are still read; the
``gtreencrypt`` command rewrites them with the current key.

A stored value is ``base64(nonce + tag + ciphertext)`` (AES EAX, 16-byte
nonce and tag), whatever the key: the format did not change.
"""
import base64
import binascii
import io
import json
import os
from base64 import b64encode, b64decode

from Crypto.Cipher import AES
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models, transaction
from django.db.models import Value
from django.db.models.functions import Cast

#: The AES key sizes, in bytes.
KEY_SIZES = (16, 24, 32)


def create_key(size=32):
    """A new random key, as ``GT_ENCRYPTION_KEY`` takes it (base64)."""
    key = os.urandom(size)
    base64_encoded = base64.b64encode(key)
    return base64_encoded.decode('utf-8')


def get_salt_session(size=16):
    """The legacy key: the first ``size`` bytes of ``SECRET_KEY``."""
    key = settings.SECRET_KEY.encode()
    if len(key) > size:
        return key[:size]
    return key


def _decode_key(text):
    try:
        key = b64decode(text, validate=True)
    except (binascii.Error, TypeError, ValueError):
        key = None
    if key is None or len(key) not in KEY_SIZES:
        raise ImproperlyConfigured(
            'GT_ENCRYPTION_KEY must be the base64 of 16, 24 or 32 bytes (or a '
            'list of them); djgentelella.fields.secure.create_key() makes one.')
    return key


def configured_keys():
    """The keys of ``GT_ENCRYPTION_KEY``, the one that encrypts first; empty
    when it is not set."""
    value = getattr(settings, 'GT_ENCRYPTION_KEY', None)
    if not value:
        return []
    if isinstance(value, (str, bytes)):
        value = [value]
    return [_decode_key(item) for item in value]


def encryption_key():
    """The key new values are encrypted with."""
    keys = configured_keys()
    return keys[0] if keys else get_salt_session()


def decryption_keys():
    """Every key a stored value is tried with, in order: those of
    ``GT_ENCRYPTION_KEY`` and then the legacy one of ``SECRET_KEY`` (when it
    is long enough to be an AES key)."""
    keys = configured_keys()
    legacy = get_salt_session()
    if len(legacy) in KEY_SIZES and legacy not in keys:
        keys.append(legacy)
    return keys


def salt_encrypt(message, session_key=None):
    """``base64(nonce + tag + ciphertext)`` of ``message`` with
    ``session_key``, by default :func:`encryption_key`."""
    if isinstance(message, str):
        message = message.encode()
    if session_key is None:
        session_key = encryption_key()
    file_out = io.BytesIO()
    cipher_aes = AES.new(session_key, AES.MODE_EAX)
    ciphertext, tag = cipher_aes.encrypt_and_digest(message)
    [file_out.write(x) for x in (cipher_aes.nonce, tag, ciphertext)]
    file_out.seek(0)
    return b64encode(file_out.read())


def _split(message):
    file_in = io.BytesIO(b64decode(message))
    file_in.seek(0)
    return [file_in.read(x) for x in (16, 16, -1)]


def decrypt_with_key(message, keys=None):
    """``(plaintext, key)``: ``message`` decrypted with the first of ``keys``
    (by default :func:`decryption_keys`) whose tag checks. ``ValueError``
    when none does."""
    nonce, tag, ciphertext = _split(message)
    keys = decryption_keys() if keys is None else keys
    for key in keys:
        try:
            cipher_aes = AES.new(key, AES.MODE_EAX, nonce)
            return cipher_aes.decrypt_and_verify(ciphertext, tag), key
        except ValueError:
            continue
    raise ValueError('MAC check failed: no encryption key decrypts the value')


def salt_decrypt(message):
    if message is None:
        return None
    return decrypt_with_key(message)[0]


class GTEncryptedText(models.TextField):
    """
    Encrypt data using AES and secure django key use in models like:
    in models.py

        class MyModel(models.Model):
            my_secret = GTEncryptedText(null=True, blank=True)

    """

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        if isinstance(value, str):
            value = value.encode()
        return salt_decrypt(value)

    def pre_save(self, model_instance, add):
        field = getattr(model_instance, self.attname)
        if field is None:
            return None
        dev = salt_encrypt(field)
        if isinstance(dev, bytes):
            dev = dev.decode()
        return dev

    def value_from_object(self, obj):
        dev = super(GTEncryptedText, self).value_from_object(obj)
        return dev.decode() if dev is not None else None


class GTEncryptedJSONField(models.JSONField):
    """
    Encrypt data using AES and secure django key use in models can store JSON objects:
    in models.py

        class MyModel(models.Model):
            my_secret = GTEncryptedJSONField(null=True, blank=True)

    """

    def get_prep_value(self, value):
        # encrypt the JSON before save to the database
        if value is not None:
            value = json.dumps(value)
            encrypted_value = salt_encrypt(
                super().get_prep_value(value).encode('utf-8')
            )
            return encrypted_value.decode('utf-8')  # Store as text in DB
        return value

    def from_db_value(self, value, expression, connection):
        # decrypt when loading from the database
        if value is not None:
            decrypted_value = salt_decrypt(value.encode('utf-8'))
            return super().from_db_value(
                decrypted_value.decode('utf-8'), expression, connection
            )
        return value


# -- re-encrypting --------------------------------------------------------------

ENCRYPTED_FIELDS = (GTEncryptedText, GTEncryptedJSONField)


def encrypted_fields(model_list=None):
    """``[(model, field)]`` of every encrypted field of ``model_list``, by
    default of every installed model."""
    if model_list is None:
        model_list = apps.get_models()
    return [(model, field) for model in model_list
            for field in model._meta.concrete_fields
            if isinstance(field, ENCRYPTED_FIELDS)]


def reencrypt(model, field, dry_run=False):
    """Encrypt again with :func:`encryption_key` the values of ``field`` that
    another key (the legacy one of ``SECRET_KEY``, an older
    ``GT_ENCRYPTION_KEY``) encrypted.

    The stored text is read as it is and written back with ``update()``, so
    no ``save()``, signal or ``auto_now`` runs. Returns ``{'reencrypted',
    'current', 'unreadable'}``, the number of rows of each kind; an unreadable
    value (no key decrypts it) is left as it was.
    """
    counts = {'reencrypted': 0, 'current': 0, 'unreadable': 0}
    current = encryption_key()
    output = (models.JSONField() if isinstance(field, models.JSONField)
              else models.TextField())
    rows = model._base_manager.exclude(**{field.attname + '__isnull': True}) \
        .annotate(gt_raw=Cast(field.attname, models.TextField())) \
        .values_list('pk', 'gt_raw')
    with transaction.atomic(using=rows.db):
        for pk, raw in rows.iterator():
            try:
                plaintext, key = decrypt_with_key(raw.encode())
            except (ValueError, binascii.Error):
                counts['unreadable'] += 1
                continue
            if key == current:
                counts['current'] += 1
                continue
            counts['reencrypted'] += 1
            if not dry_run:
                value = salt_encrypt(plaintext, current).decode()
                model._base_manager.filter(pk=pk).update(
                    **{field.attname: Value(value, output_field=output)})
    return counts
