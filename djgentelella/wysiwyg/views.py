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
        path = default_storage.save(os.path.join(
            upload_to+folder, the_file.name), the_file)
        return path
@csrf_exempt
def image_upload(request):
    path = default_storage.url(upload(request, '/images'))
    link= path[path.index("/media/"):len(path)]
    return HttpResponse(json.dumps({'link': link}), content_type="application/json")



