from django.http import HttpResponse
from django.conf import settings
from django.core.files.storage import default_storage
import os
import json

def upload(request, folder):
    if 'file' in request.FILES:
        the_file = request.FILES['file']
        upload_to = getattr(settings,'FROALA_UPLOAD_PATH')
        path = default_storage.save(os.path.join(
            upload_to+folder, the_file.name), the_file)
        return path

def image_upload(request):
    link = default_storage.url(upload(request, '/images'))
    return HttpResponse(json.dumps({'link': link}), content_type="application/json")


def video_upload(request):
   link = default_storage.url(upload(request, '/videos'))
   return HttpResponse(json.dumps({'link': link}), content_type="application/json")

def file_upload(request):
   link = default_storage.url(upload(request, '/files'))
   return HttpResponse(json.dumps({'link': link}), content_type="application/json")