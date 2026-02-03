"""
Utility functions for chunked upload management.
"""
from django.utils import timezone

from djgentelella.chunked_upload.constants import UPLOADING, COMPLETE
from djgentelella.models import ChunkedUpload
from djgentelella.settings import EXPIRATION_DELTA


def get_expired_uploads():
    """
    Get queryset of chunked uploads that have expired.

    Returns:
        QuerySet: ChunkedUpload objects that have expired.
    """
    return ChunkedUpload.objects.filter(
        created_on__lt=(timezone.now() - EXPIRATION_DELTA)
    )


def delete_expired_uploads(exclude_ids=None):
    """
    Delete chunked uploads that have already expired.

    Args:
        exclude_ids: Optional list of upload IDs to exclude from deletion.

    Returns:
        dict: A dictionary with 'complete' and 'uploading' keys containing
              the count of deleted uploads for each status.
    """
    count = {UPLOADING: 0, COMPLETE: 0}
    qs = get_expired_uploads()

    if exclude_ids:
        qs = qs.exclude(id__in=exclude_ids)

    for chunked_upload in qs:
        count[chunked_upload.status] += 1
        chunked_upload.delete()

    return {
        'complete': count[COMPLETE],
        'uploading': count[UPLOADING],
    }
