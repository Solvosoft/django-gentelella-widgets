import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from djgentelella.designs.models import Page, normalize_path

from ._common import get_site


def dump(document):
    return json.dumps(document, indent=2, ensure_ascii=False) + '\n'


class Command(BaseCommand):
    help = ('Write the design document of published pages back to JSON files, '
            'the format gtdesigns_publish and djgentelella-editor read.')

    def add_arguments(self, parser):
        parser.add_argument('path', nargs='?',
                            help='Path of one page under designs/. Without it, '
                                 'every page of the site is exported to --output.')
        parser.add_argument('--site', help='Domain of the Site; without it, the '
                                           'global pages.')
        parser.add_argument('--output', '-o',
                            help='File for one page (stdout without it), '
                                 'directory for all of them.')

    def handle(self, *args, **options):
        site = get_site(options['site'])
        if options['path']:
            page = Page.objects.filter(site=site, path=normalize_path(
                options['path'])).first()
            if page is None:
                raise CommandError('No page at designs/%s.' % options['path'])
            if options['output']:
                Path(options['output']).write_text(dump(page.document),
                                                   encoding='utf-8')
            else:
                self.stdout.write(dump(page.document), ending='')
            return
        if not options['output']:
            raise CommandError('Give a page path, or --output <directory> to '
                               'export every page.')
        directory = Path(options['output'])
        directory.mkdir(parents=True, exist_ok=True)
        count = 0
        for page in Page.objects.filter(site=site):
            name = page.path.replace('/', '__') + '.json'
            (directory / name).write_text(dump(page.document), encoding='utf-8')
            count += 1
        self.stdout.write(self.style.SUCCESS('Exported %d page(s) to %s.' % (
            count, directory)))
