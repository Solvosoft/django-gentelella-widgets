"""Import the translations of pages, menus and LOVs from JSON (C20)."""

import json

from django.core.management.base import BaseCommand, CommandError

from djgentelella.translations import transfer


class Command(BaseCommand):
    help = ('Import a JSON file of translations (the format of '
            'gttranslations_export). Nothing is written when it has errors.')

    def add_arguments(self, parser):
        parser.add_argument('file')
        parser.add_argument('--dry-run', action='store_true',
                            help='Only validate the file.')

    def handle(self, *args, **options):
        try:
            with open(options['file'], encoding='utf-8') as source:
                data = json.load(source)
        except (OSError, ValueError) as error:
            raise CommandError('Cannot read %s: %s' % (options['file'], error))
        summary, errors = transfer.import_translations(
            data, dry_run=options['dry_run'])
        if errors:
            raise CommandError('\n'.join(str(error) for error in errors))
        self.stdout.write('%s: %d pages, %d menu items, %d lists' % (
            'Valid' if options['dry_run'] else 'Imported',
            summary['pages'], summary['menus'], summary['lovs']))
