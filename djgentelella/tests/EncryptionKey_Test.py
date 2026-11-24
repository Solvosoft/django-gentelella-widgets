"""GTEncryptedText and GTEncryptedJSONField with GT_ENCRYPTION_KEY: what the
SECRET_KEY key encrypted is still read, and gtreencrypt rewrites it."""
from io import StringIO

from django.apps.registry import Apps
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command
from django.db import connection, models
from django.test import SimpleTestCase, TestCase, override_settings

from djgentelella.fields import secure
from djgentelella.fields.secure import (
    GTEncryptedJSONField,
    GTEncryptedText,
    create_key,
    decrypt_with_key,
    encrypted_fields,
    reencrypt,
    salt_decrypt,
    salt_encrypt,
)

OLD_SECRET = 'an-old-secret-key-of-the-project-0123456789'
NEW_KEY = create_key()
NEWER_KEY = create_key(16)


class Secret(models.Model):
    """A table of its own, out of the project's registry and migrations."""

    note = GTEncryptedText(null=True, blank=True)
    data = GTEncryptedJSONField(null=True, blank=True)

    class Meta:
        app_label = 'djgentelella'
        apps = Apps()


def raw(pk, field):
    """The text stored in the column, as the database has it."""
    with connection.cursor() as cursor:
        cursor.execute('SELECT %s FROM %s WHERE id = %%s' % (
            connection.ops.quote_name(field),
            connection.ops.quote_name(Secret._meta.db_table)), [pk])
        value = cursor.fetchone()[0]
    return value if isinstance(value, str) else str(value)


@override_settings(SECRET_KEY=OLD_SECRET)
class KeysTests(SimpleTestCase):
    def test_without_the_setting_the_key_is_the_secret_key(self):
        self.assertEqual(secure.encryption_key(), OLD_SECRET.encode()[:16])
        self.assertEqual(secure.decryption_keys(), [OLD_SECRET.encode()[:16]])

    @override_settings(GT_ENCRYPTION_KEY=NEW_KEY)
    def test_the_setting_encrypts_and_the_old_key_still_reads(self):
        self.assertEqual(len(secure.encryption_key()), 32)
        self.assertNotEqual(secure.encryption_key(), OLD_SECRET.encode()[:16])
        self.assertEqual(secure.decryption_keys()[1:], [OLD_SECRET.encode()[:16]])

    def test_a_value_of_the_old_key_is_read_with_the_new_one_set(self):
        old = salt_encrypt('secret')
        with override_settings(GT_ENCRYPTION_KEY=NEW_KEY):
            self.assertEqual(salt_decrypt(old), b'secret')
            new = salt_encrypt('secret')
            self.assertEqual(salt_decrypt(new), b'secret')
        # The new value needs the new key: the SECRET_KEY one does not open it.
        with self.assertRaises(ValueError):
            salt_decrypt(new)

    def test_the_same_format(self):
        with override_settings(GT_ENCRYPTION_KEY=NEW_KEY):
            value = salt_encrypt('x')
            plaintext, key = decrypt_with_key(value)
        self.assertEqual(plaintext, b'x')
        self.assertEqual(len(secure.b64decode(value)), 16 + 16 + 1)

    def test_a_list_rotates_the_keys(self):
        with override_settings(GT_ENCRYPTION_KEY=NEW_KEY):
            older = salt_encrypt('rotated')
        with override_settings(GT_ENCRYPTION_KEY=[NEWER_KEY, NEW_KEY]):
            self.assertEqual(len(secure.encryption_key()), 16)
            self.assertEqual(salt_decrypt(older), b'rotated')
            self.assertEqual(len(secure.decryption_keys()), 3)

    def test_an_invalid_key_is_a_configuration_error(self):
        for value in ('not base64!', 'c2hvcnQ=', ['x' * 44], 'a' * 45):
            with self.subTest(value=value), override_settings(GT_ENCRYPTION_KEY=value):
                with self.assertRaisesMessage(ImproperlyConfigured,
                                              'GT_ENCRYPTION_KEY'):
                    salt_encrypt('x')

    def test_a_value_no_key_opens(self):
        value = salt_encrypt('x')
        with override_settings(SECRET_KEY='another-secret-key-0123456789'):
            with self.assertRaisesMessage(ValueError, 'MAC check failed'):
                salt_decrypt(value)


@override_settings(SECRET_KEY=OLD_SECRET)
class EncryptedTableTests(TestCase):
    @classmethod
    def setUpClass(cls):
        # Before the class transaction: SQLite cannot change the schema
        # inside one.
        with connection.schema_editor() as editor:
            editor.create_model(Secret)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        with connection.schema_editor() as editor:
            editor.delete_model(Secret)

    def test_the_fields_read_what_the_old_key_wrote(self):
        secret = Secret.objects.create(note='old note', data={'token': 'old'})
        with override_settings(GT_ENCRYPTION_KEY=NEW_KEY):
            again = Secret.objects.get(pk=secret.pk)
            self.assertEqual(again.note, b'old note')
            self.assertEqual(again.data, {'token': 'old'})
            # Saved again, with the new key.
            again.note = 'new note'
            again.save()
            self.assertEqual(Secret.objects.get(pk=secret.pk).note, b'new note')
        with self.assertRaises(ValueError):
            Secret.objects.get(pk=secret.pk)

    def test_reencrypt(self):
        first = Secret.objects.create(note='one', data={'a': 1})
        Secret.objects.create(note=None, data=None)
        self.assertEqual(encrypted_fields([Secret]),
                         [(Secret, Secret._meta.get_field('note')),
                          (Secret, Secret._meta.get_field('data'))])
        stored = raw(first.pk, 'note')
        with override_settings(GT_ENCRYPTION_KEY=NEW_KEY):
            note, data = encrypted_fields([Secret])
            self.assertEqual(reencrypt(*note, dry_run=True),
                             {'reencrypted': 1, 'current': 0, 'unreadable': 0})
            self.assertEqual(raw(first.pk, 'note'), stored)
            self.assertEqual(reencrypt(*note), {'reencrypted': 1, 'current': 0,
                                                'unreadable': 0})
            self.assertEqual(reencrypt(*data), {'reencrypted': 1, 'current': 0,
                                                'unreadable': 0})
            self.assertEqual(reencrypt(*note), {'reencrypted': 0, 'current': 1,
                                                'unreadable': 0})
            self.assertNotEqual(raw(first.pk, 'note'), stored)
        # Only the new key opens them now: a new SECRET_KEY does not matter.
        with override_settings(GT_ENCRYPTION_KEY=NEW_KEY,
                               SECRET_KEY='a-rotated-secret-key-0123456789'):
            again = Secret.objects.get(pk=first.pk)
            self.assertEqual((again.note, again.data), (b'one', {'a': 1}))
        with self.assertRaises(ValueError):
            Secret.objects.get(pk=first.pk)

    def test_an_unreadable_value_is_left_alone(self):
        secret = Secret.objects.create(note='lost')
        stored = raw(secret.pk, 'note')
        with override_settings(GT_ENCRYPTION_KEY=NEW_KEY,
                               SECRET_KEY='a-rotated-secret-key-0123456789'):
            note, _data = encrypted_fields([Secret])
            self.assertEqual(reencrypt(*note), {'reencrypted': 0, 'current': 0,
                                                'unreadable': 1})
        self.assertEqual(raw(secret.pk, 'note'), stored)


class ReencryptCommandTests(SimpleTestCase):
    def test_the_project_without_encrypted_fields(self):
        out = StringIO()
        call_command('gtreencrypt', stdout=out)
        self.assertIn('No encrypted fields.', out.getvalue())

    def test_an_unknown_model(self):
        with self.assertRaises(CommandError):
            call_command('gtreencrypt', 'nowhere.Model', stdout=StringIO())
