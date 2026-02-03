from django.core.management.base import BaseCommand

from djgentelella.chunked_upload.constants import UPLOADING, COMPLETE
from djgentelella.chunked_upload.utils import get_expired_uploads, delete_expired_uploads


class Command(BaseCommand):
    help = 'Deletes chunked uploads that have already expired.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interactive',
            action='store_true',
            dest='interactive',
            default=False,
            help='Prompt confirmation before each deletion.',
        )

    def handle(self, *args, **options):
        interactive = options.get('interactive')

        if interactive:
            result = self._handle_interactive()
        else:
            result = delete_expired_uploads()

        self.stdout.write(
            self.style.SUCCESS(
                f"{result['complete']} complete uploads were deleted."
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{result['uploading']} incomplete uploads were deleted."
            )
        )

    def _handle_interactive(self):
        """Handle interactive deletion with user confirmation."""
        count = {UPLOADING: 0, COMPLETE: 0}
        exclude_ids = []

        for chunked_upload in get_expired_uploads():
            prompt = f'Do you want to delete {chunked_upload}? (y/n): '
            answer = input(prompt).lower()
            while answer not in ('y', 'n'):
                answer = input(prompt).lower()

            if answer == 'n':
                exclude_ids.append(chunked_upload.id)
            else:
                count[chunked_upload.status] += 1
                chunked_upload.delete()

        return {
            'complete': count[COMPLETE],
            'uploading': count[UPLOADING],
        }
