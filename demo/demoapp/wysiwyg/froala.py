import json
# from django.http import JsonResponse
from django.http import HttpResponse
from django.conf import settings
import os
from django.utils.translation import ugettext_lazy as _
from django.utils.module_loading import import_string
from django.core.files.storage import default_storage


def upload(request, option):
    if 'file' in request.FILES:
        the_file = request.FILES['file']
        upload_to = getattr(settings, 'FROALA_UPLOAD_PATH',
                            'uploads/froala_editor/'+""+option)
        path = default_storage.save(os.path.join(
            upload_to, the_file.name), the_file)
        return path

def image_upload(request):
    path=upload(request, 'images')
    link = default_storage.url(path)
    return HttpResponse(json.dumps({'link': link}), content_type="application/json")


def video_upload(request):
   path=upload(request, 'video')
   link = default_storage.url(path)
   return HttpResponse(json.dumps({'link': link}), content_type="application/json")

def file_upload(request):
   path=upload(request, 'doc')
   link = default_storage.url(path)
   return HttpResponse(json.dumps({'link': link}), content_type="application/json")
