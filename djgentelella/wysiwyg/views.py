import os

from django.conf import settings
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


def upload(request, folder):
    if 'file' in request.FILES:
        the_file = request.FILES['file']
        upload_to = getattr(settings,'SUMMERNOTE_UPLOAD_PATH')
        path = default_storage.save(os.path.join(
            upload_to+folder, the_file.name), the_file)
        return path

@csrf_exempt
def image_upload(request):
    path = upload(request, '/images')
    link=path.replace(settings.MEDIA_ROOT, settings.MEDIA_URL)
    return JsonResponse({'link': link})

