"""Write the translations of pages, menus and LOVs as JSON (C20)."""

import json

from django.core.management.base import BaseCommand, CommandError

from djgentelella import translations as core
from djgentelella.translations import transfer


class Command(BaseCommand):
    help = ('Export the translations of design pages, menu items and LOVs as '
            'the JSON of djgentelella.translations.transfer.')

    def add_arguments(self, parser):
        parser.add_argument('--language', action='append', dest='languages',
                            help='Only this language (repeatable).')
        parser.add_argument('--section', action='append', dest='sections',
                            choices=transfer.SECTIONS,
                            help='Only pages, menus or lovs (repeatable).')
        parser.add_argument('--only-translated', action='store_true',
                            help='Leave out the texts without a translation.')
        parser.add_argument('--output', '-o', help='File to write (default: stdout).')

    def handle(self, *args, **options):
        languages = options['languages']
        for code in languages or ():
            if code not in core.language_codes():
                raise CommandError('Unknown language %r: the project offers %s'
                                   % (code, ', '.join(core.language_codes())))
        data = transfer.export_translations(
            languages=languages, sections=options['sections'] or transfer.SECTIONS,
            empty=not options['only_translated'])
        text = json.dumps(data, ensure_ascii=False, indent=2)
        if options['output']:
            with open(options['output'], 'w', encoding='utf-8') as output:
                output.write(text + '\n')
        else:
            self.stdout.write(text)
