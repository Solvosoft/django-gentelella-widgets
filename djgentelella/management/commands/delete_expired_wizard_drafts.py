from django.core.management.base import BaseCommand

from djgentelella.models import WizardDraft


class Command(BaseCommand):
    help = ('Deletes the wizard drafts (djgentelella.wizard) not changed for '
            'longer than GT_WIZARD_DRAFT_EXPIRATION.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Only count them.')

    def handle(self, *args, **options):
        expired = WizardDraft.objects.expired()
        count = expired.count()
        if not options['dry_run']:
            expired.delete()
        self.stdout.write(self.style.SUCCESS(
            '%d expired wizard drafts %s.' % (
                count, 'would be deleted' if options['dry_run'] else 'deleted')))
