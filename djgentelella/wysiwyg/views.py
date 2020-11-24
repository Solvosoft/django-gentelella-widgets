from django.http import HttpResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from django.core.files.storage import default_storage
import os
import json

def upload(request, folder):
    if 'file' in request.FILES:
        the_file = request.FILES['file']
        upload_to = getattr(settings,'SUMMERNOTE_UPLOAD_PATH')
        default_storage.save(os.path.join(upload_to, the_file.name), the_file)
        path = "/media/summernote/"+the_file.name
        return path
@csrf_exempt
def image_upload(request):
   link = upload(request, 'img')
   return HttpResponse(json.dumps({'link': link}), content_type="application/json")
