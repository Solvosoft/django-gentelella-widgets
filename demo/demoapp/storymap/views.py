from django.shortcuts import render

from demoapp.storymap.forms import GigapixelForm, MapbasedForm


def gigapixel_view(request):
    form = GigapixelForm()
    if request.method == 'POST':
        form = GigapixelForm(request.POST)
        if form.is_valid():
            form.save()
    return render(request, 'gentelella/index.html', {'form': form})


def mapbased_view(request):
    form = MapbasedForm()
    if request.method == 'POST':
        form = MapbasedForm(request.POST)
        if form.is_valid():
            form.save()
    return render(request, 'gentelella/index.html', {'form': form})
