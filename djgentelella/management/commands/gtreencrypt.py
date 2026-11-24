"""Encrypt again with the current key the values of GTEncryptedText and
GTEncryptedJSONField that an older key encrypted."""
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError

from djgentelella.fields.secure import encrypted_fields, reencrypt


class Command(BaseCommand):
    help = ('Encrypt again with GT_ENCRYPTION_KEY (its first key) the values of '
            'the encrypted fields that the legacy SECRET_KEY key, or an older '
            'GT_ENCRYPTION_KEY, encrypted.')

    def add_arguments(self, parser):
        parser.add_argument(
            'models', nargs='*', metavar='app_label.Model',
            help='Only these models (by default, every installed one).')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Count the values to re-encrypt without writing them.')

    def handle(self, *args, **options):
        try:
            model_list = [apps.get_model(label)
                          for label in options['models']] or None
        except (LookupError, ValueError) as error:
            raise CommandError(str(error))
        fields = encrypted_fields(model_list)
        if not fields:
            self.stdout.write('No encrypted fields.')
            return
        unreadable = 0
        for model, field in fields:
            counts = reencrypt(model, field, dry_run=options['dry_run'])
            unreadable += counts['unreadable']
            self.stdout.write(
                '%s.%s: %d %s, %d current, %d unreadable' % (
                    model._meta.label, field.name, counts['reencrypted'],
                    'to re-encrypt' if options['dry_run'] else 're-encrypted',
                    counts['current'], counts['unreadable']))
        if unreadable:
            raise CommandError(
                '%d values could not be decrypted with any key (GT_ENCRYPTION_KEY '
                'or the SECRET_KEY one) and were left as they were.' % unreadable)
