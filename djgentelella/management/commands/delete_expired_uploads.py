from djgentelella.chunked_upload.constants import UPLOADING, COMPLETE
from djgentelella.models import ChunkedUpload
from djgentelella.settings import EXPIRATION_DELTA
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

prompt_msg = _('Do you want to delete {obj}?')


class Command(BaseCommand):
    # Has to be a ChunkedUpload subclass
    model = ChunkedUpload
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

        count = {UPLOADING: 0, COMPLETE: 0}
        qs = self.model.objects.all()
        qs = qs.filter(created_on__lt=(timezone.now() - EXPIRATION_DELTA))

        for chunked_upload in qs:
            if interactive:
                prompt = prompt_msg.format(obj=chunked_upload) + ' (y/n): '
                answer = input(prompt).lower()
                while answer not in ('y', 'n'):
                    answer = input(prompt).lower()
                if answer == 'n':
                    continue

            count[chunked_upload.status] += 1
            # Deleting objects individually to call delete method explicitly
            chunked_upload.delete()

        self.stdout.write(
            self.style.SUCCESS(f'{count[COMPLETE]} complete uploads were deleted.')
        )
        self.stdout.write(
            self.style.SUCCESS(f'{count[UPLOADING]} incomplete uploads were deleted.')
        )
