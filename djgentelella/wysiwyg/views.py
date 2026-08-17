from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.http.response import JsonResponse


def upload(request, folder):
    if 'file' not in request.FILES:
        return None
    the_file = request.FILES['file']
    # TINYMCE_UPLOAD_PATH may be absolute; default_storage.save() expects a
    # name relative to MEDIA_ROOT, so make it relative (Django rejects
    # absolute paths as a path-traversal attempt).
    upload_to = Path(getattr(settings, 'TINYMCE_UPLOAD_PATH', 'tinymce'))
    media_root = Path(settings.MEDIA_ROOT)
    try:
        upload_to = upload_to.relative_to(media_root)
    except ValueError:
        pass
    name = str(Path(upload_to) / folder / the_file.name)
    return default_storage.save(name, the_file)


def image_upload(request):
    # Root-relative media URL (no scheme/host) so stored content is
    # domain-independent and survives a domain change / multi-site setup.
    path = upload(request, 'images')
    return JsonResponse({'link': default_storage.url(path)})


def video_upload(request):
    path = upload(request, 'videos')
    return JsonResponse({'link': default_storage.url(path)})
