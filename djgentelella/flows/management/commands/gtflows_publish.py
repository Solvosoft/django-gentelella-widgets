"""Publish a JSON flow definition (``flows/schema_v2.json``) as a new
FlowDefinition version, without restarting anything."""

import json

from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from djgentelella.flows.definitions import publish_definition


class Command(BaseCommand):
    help = 'Publish a JSON flow definition as a new version.'

    def add_arguments(self, parser):
        parser.add_argument('file', help='The JSON document.')
        parser.add_argument('--site', help='Domain of the Site it belongs to '
                                           '(global by default).')
        parser.add_argument('--inactive', action='store_true',
                            help='Store it without starting instances with it.')

    def handle(self, *args, **options):
        with open(options['file'], encoding='utf-8') as handle:
            document = json.load(handle)
        site = None
        if options['site']:
            try:
                site = Site.objects.get(domain=options['site'])
            except Site.DoesNotExist:
                raise CommandError('No site %r' % options['site']) from None
        try:
            definition = publish_definition(document, site=site,
                                            activate=not options['inactive'])
        except ImproperlyConfigured as error:
            raise CommandError(str(error)) from None
        self.stdout.write('Published %s' % definition)
