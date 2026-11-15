import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from djgentelella.designs.publishing import publish

from ._common import get_site


class Command(BaseCommand):
    help = ('Validate a design JSON file and publish it as a page under designs/. '
            'Nothing is saved when the design has errors.')

    def add_arguments(self, parser):
        parser.add_argument('file', help='The design document (.json).')
        parser.add_argument('--site', help='Domain of the Site the page belongs to; '
                                           'without it the page is global.')
        parser.add_argument('--path', help='Path under designs/; by default the '
                                           'meta.url of the design.')
        parser.add_argument('--user', help='Username recorded as the publisher. '
                                           'Templates in html nodes and assets.js '
                                           'need one with the publish permissions.')
        parser.add_argument('--draft', action='store_true',
                            help='Save the page unpublished.')

    def handle(self, *args, **options):
        path = Path(options['file'])
        try:
            document = json.loads(path.read_text(encoding='utf-8'))
        except OSError as error:
            raise CommandError('Cannot read %s: %s' % (path, error)) from None
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise CommandError('%s is not valid JSON: %s' % (path, error)) from None
        user = None
        if options['user']:
            user_model = get_user_model()
            try:
                user = user_model.objects.get(**{
                    user_model.USERNAME_FIELD: options['user']})
            except user_model.DoesNotExist:
                raise CommandError('No user %r.' % options['user']) from None
        page, errors = publish(document, site=get_site(options['site']),
                               path=options['path'], user=user,
                               published=not options['draft'])
        if errors:
            raise CommandError('%s is not a valid design:\n%s' % (
                path, '\n'.join('  %s' % (error,) for error in errors)))
        self.stdout.write(self.style.SUCCESS('%s %s as designs/%s (page %d).' % (
            'Saved' if options['draft'] else 'Published', path, page.path, page.pk)))
