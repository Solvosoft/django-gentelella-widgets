"""
Utility functions for chunked upload management.
"""
from django.db.models import Q
from django.utils import timezone

from djgentelella.chunked_upload.constants import UPLOADING, COMPLETE
from djgentelella.models import ChunkedUpload, WizardDraft
from djgentelella.settings import EXPIRATION_DELTA


def get_expired_uploads():
    """
    Get queryset of chunked uploads that have expired.

    The uploads a live wizard draft keeps (``WizardDraft.uploads``) are left
    out: the draft still needs their files.

    Returns:
        QuerySet: ChunkedUpload objects that have expired.
    """
    kept = {token for tokens in WizardDraft.objects.live().exclude(uploads=[])
            .values_list('uploads', flat=True) for token in tokens or ()}
    return ChunkedUpload.objects.filter(
        created_on__lt=(timezone.now() - EXPIRATION_DELTA)
    ).exclude(upload_id__in=kept)


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


#: For :func:`find_upload`: the upload of ``token`` whoever uploaded it.
ANY_USER = object()


def find_upload(token, user):
    """The finished ``ChunkedUpload`` of ``token`` that ``user`` uploaded, or
    ``None``.

    ``user`` is who presents the token, usually ``request.user``: a signed-in
    user takes only their own uploads, and an anonymous one (or ``None``) only
    those without a user, the uploads of anonymous visitors. :data:`ANY_USER`
    takes the upload whoever uploaded it, for code that has no request to ask
    (a serializer used outside one). An upload that did not finish
    (``UPLOADING``) is never taken: its file is only part of the document.

    Finished is ``status=COMPLETE`` or a ``completed_on``: the upload views
    set both when the last chunk arrives, and code that creates a
    ``ChunkedUpload`` by hand (a generated file, a test) often sets only
    ``completed_on`` and leaves ``status`` at its default, ``UPLOADING``.
    """
    if not isinstance(token, str) or not token:
        return None
    uploads = ChunkedUpload.objects.filter(
        Q(status=COMPLETE) | Q(completed_on__isnull=False), upload_id=token)
    if user is not ANY_USER:
        if user is not None and user.is_authenticated:
            uploads = uploads.filter(user=user)
        else:
            uploads = uploads.filter(user__isnull=True)
    return uploads.first()


def request_user(context):
    """Who presents an upload token to a DRF serializer: the user of the
    request in its ``context``, the ``user`` of the context (the websocket
    consumer of the digital signature passes it), or :data:`ANY_USER` when the
    serializer runs without either."""
    context = context or {}
    request = context.get('request')
    if request is not None:
        return getattr(request, 'user', None)
    if 'user' in context:
        return context['user']
    return ANY_USER
