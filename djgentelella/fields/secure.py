import base64
import io
import json
import os
from base64 import b64encode, b64decode

from Crypto.Cipher import AES
from django.conf import settings
from django.db import models


def create_key(size=32):
    key = os.urandom(size)
    base64_encoded = base64.b64encode(key)
    return base64_encoded.decode("utf-8")


def get_salt_session(size=16):
    key = settings.SECRET_KEY.encode()
    if len(key) > size:
        return key[:size]
    return key


def salt_encrypt(message, session_key=None):
    if type(message) == str:
        message = message.encode()
    session_key = get_salt_session()
    file_out = io.BytesIO()
    cipher_aes = AES.new(session_key, AES.MODE_EAX)
    ciphertext, tag = cipher_aes.encrypt_and_digest(message)
    [file_out.write(x) for x in (cipher_aes.nonce, tag, ciphertext)]
    file_out.seek(0)
    return b64encode(file_out.read())


def salt_decrypt(message):
    if message is None:
        return None
    raw_cipher_data = b64decode(message)
    file_in = io.BytesIO(raw_cipher_data)
    file_in.seek(0)

    nonce, tag, ciphertext = [file_in.read(x) for x in (16, 16, -1)]
    session_key = get_salt_session()
    cipher_aes = AES.new(session_key, AES.MODE_EAX, nonce)
    decrypted = cipher_aes.decrypt_and_verify(ciphertext, tag)
    return decrypted


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
        if type(dev) == bytes:
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
                super().get_prep_value(value).encode("utf-8")
            )
            return encrypted_value.decode("utf-8")  # Store as text in DB
        return value

    def from_db_value(self, value, expression, connection):
        # decrypt when loading from the database
        if value is not None:
            decrypted_value = salt_decrypt(value.encode("utf-8"))
            return super().from_db_value(
                decrypted_value.decode("utf-8"), expression, connection
            )
        return value
