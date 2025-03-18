from django.shortcuts import render

from demoapp.media_upload.forms import MediaUploadForm


def mediaupload_view(request):
    form = MediaUploadForm()
    if request.method == 'POST':
        form = MediaUploadForm(request.POST, files=request.FILES)
        if form.is_valid():
            print(form.cleaned_data['video_record'])
    return render(request, 'gentelella/index.html', {'form': form})
