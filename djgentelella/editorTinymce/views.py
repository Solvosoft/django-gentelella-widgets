from django.http import HttpResponse
from django.conf import settings
from django.core.files.storage import default_storage
import os
import json
from django.http.response import JsonResponse

def upload(request, folder):
    if 'file' in request.FILES:
        the_file = request.FILES['file']
        upload_to = getattr(settings,'TINYMCE_UPLOAD_PATH')
        path = default_storage.save(os.path.join(
            upload_to+folder, the_file.name), the_file)
        return path

def image_upload(request):
    path = upload(request, '/images')
    link=path.replace(settings.MEDIA_ROOT, settings.MEDIA_URL)
    return JsonResponse({'link': link})

def video_upload(request):
   path = upload(request, '/videos')
   link=path.replace(settings.MEDIA_ROOT, settings.MEDIA_URL)
   return JsonResponse({'link': link})
