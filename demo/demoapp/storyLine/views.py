from django.shortcuts import render
from demoapp.storyLine.forms import StoryLineForm


def storyline_view(request):
    form = StoryLineForm()
    if request.method == 'POST':
        form = StoryLineForm(request.POST)
        if form.is_valid():
            form.save()
    return render(request, 'gentelella/index.html', {'form': form})
