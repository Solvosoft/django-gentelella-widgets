from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.http.response import JsonResponse


def upload(request, folder):
    if 'file' in request.FILES:
        the_file = request.FILES['file']
        upload_to = getattr(settings, 'TINYMCE_UPLOAD_PATH')
        if not isinstance(upload_to, Path):
            upload_to = Path(upload_to)
        path = default_storage.save(upload_to / folder / the_file.name, the_file)
        return path


def image_upload(request):
    path = upload(request, 'images')
    link = path.replace(str(settings.MEDIA_ROOT), settings.MEDIA_URL).replace("//", "/")
    link = "%s://%s%s%s" % (request.scheme, request.get_host(), settings.MEDIA_URL, link)
    return JsonResponse({'link': link})


def video_upload(request):
    path = upload(request, 'videos')
    link = path.replace(str(settings.MEDIA_ROOT), settings.MEDIA_URL).replace("//", "/")
    link = "%s://%s%s%s" % (request.scheme, request.get_host(), settings.MEDIA_URL, link)
    return JsonResponse({'link': link})
