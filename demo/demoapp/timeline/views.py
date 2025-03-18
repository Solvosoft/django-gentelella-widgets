from django.shortcuts import render

from demoapp.timeline.forms import TimelineForm


def timeline_view(request):
    form = TimelineForm()
    if request.method == 'POST':
        form = TimelineForm(request.POST)
        if form.is_valid():
            form.save()
    return render(request, 'gentelella/index.html', {'form': form})
