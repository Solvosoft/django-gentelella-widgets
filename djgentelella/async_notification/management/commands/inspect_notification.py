"""
Management command to inspect the async_notification system configuration.

Shows registered settings, contexts, model fields, and resolvers.
"""

import json

from django.core.management.base import BaseCommand

from djgentelella.async_notification.registry import get_all_contexts
from djgentelella.async_notification.resolvers import RecipientResolverRegistry
from djgentelella.async_notification import settings as notif_settings


class Command(BaseCommand):
    help = 'Inspect async_notification configuration: settings, contexts, resolvers.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--context', type=str, default='',
            help='Filter by a specific context code')
        parser.add_argument(
            '--fields', action='store_true',
            help='Show detailed model fields for each context')
        parser.add_argument(
            '--json', action='store_true',
            help='Output in JSON format')

    def handle(self, *args, **options):
        context_filter = options['context']
        show_fields = options['fields']
        output_json = options['json']

        data = {
            'settings': self._get_settings(),
            'contexts': self._get_contexts(context_filter, show_fields),
            'resolvers': self._get_resolvers(),
        }

        if output_json:
            self.stdout.write(json.dumps(data, indent=2, default=str))
        else:
            self._print_settings(data['settings'])
            self._print_contexts(data['contexts'], show_fields)
            self._print_resolvers(data['resolvers'])

    def _get_settings(self):
        setting_names = [
            'ASYNC_NOTIFICATION_BACKEND',
            'ASYNC_NOTIFICATION_MAX_PER_MAIL',
            'ASYNC_NOTIFICATION_MAX_RETRIES',
            'ASYNC_BCC',
            'ASYNC_CC',
            'ASYNC_SEND_ONLY_EMAIL',
            'ASYNC_SMTP_DEBUG',
            'ASYNC_NOTIFICATION_BASE_TEMPLATES',
            'ASYNC_NEWSLETTER_SEVER_CONFIGS',
            'ASYNC_NEWS_BASE_MODELS',
            'ASYNC_NEWSLETTER_HEADER',
            'ASYNC_NOTIFICATION_USER_LOOKUP_FIELDS',
            'ASYNC_NOTIFICATION_GROUP_LOOKUP_FIELDS',
            'ASYNC_NOTIFICATION_PERMISSION_CLASSES',
        ]
        result = {}
        for name in setting_names:
            result[name] = getattr(notif_settings, name, None)
        return result

    def _get_contexts(self, context_filter, show_fields):
        all_contexts = get_all_contexts()
        if context_filter:
            if context_filter in all_contexts:
                all_contexts = {context_filter: all_contexts[context_filter]}
            else:
                all_contexts = {}

        result = {}
        for code, config in all_contexts.items():
            entry = {
                'code': config['code'],
                'subject': config['subject'],
                'models': config['models'],
                'exclude': config['exclude'],
                'extra_variables': config['extra_variables'],
                'depth': config['depth'],
                'preview_provider': config['preview_provider'],
            }
            if show_fields:
                from djgentelella.async_notification.introspection import (
                    get_fields_for_context)
                entry['fields'] = get_fields_for_context(code)
            result[code] = entry
        return result

    def _get_resolvers(self):
        result = {}
        for domain, resolver in RecipientResolverRegistry._resolvers.items():
            result[domain] = type(resolver).__name__
        return result

    def _print_settings(self, settings_data):
        self.stdout.write(self.style.MIGRATE_HEADING('=== Settings ==='))
        for name, value in settings_data.items():
            self.stdout.write(f'  {name}: {value}')
        self.stdout.write('')

    def _print_contexts(self, contexts_data, show_fields):
        self.stdout.write(self.style.MIGRATE_HEADING(
            '=== Registered Contexts ==='))
        if not contexts_data:
            self.stdout.write('  (none)')
            self.stdout.write('')
            return

        for code, config in contexts_data.items():
            self.stdout.write(self.style.SUCCESS(f'  [{code}]'))
            self.stdout.write(f'    Subject: {config["subject"]}')
            self.stdout.write(f'    Models: {config["models"]}')
            if config['exclude']:
                self.stdout.write(f'    Exclude: {config["exclude"]}')
            if config['extra_variables']:
                self.stdout.write(
                    f'    Extra Variables: {config["extra_variables"]}')
            self.stdout.write(f'    Depth: {config["depth"]}')
            if config['preview_provider']:
                self.stdout.write(
                    f'    Preview Provider: {config["preview_provider"]}')

            if show_fields and 'fields' in config and config['fields']:
                self.stdout.write('    Fields:')
                for prefix, fields in config['fields'].items():
                    if prefix == 'extra_variables':
                        for f in fields:
                            self.stdout.write(
                                f'      {{{{ {f["name"]} }}}} '
                                f'({f["type"]}) - {f["verbose_name"]}')
                    else:
                        for f in fields:
                            self.stdout.write(
                                f'      {{{{ {f["name"]} }}}} '
                                f'[{f["type"]}] {f["verbose_name"]}')
            self.stdout.write('')

    def _print_resolvers(self, resolvers_data):
        self.stdout.write(self.style.MIGRATE_HEADING('=== Resolvers ==='))
        if not resolvers_data:
            self.stdout.write('  (none)')
        else:
            for domain, cls_name in resolvers_data.items():
                self.stdout.write(f'  @{domain} -> {cls_name}')
        self.stdout.write('')
