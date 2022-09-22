from django.shortcuts import render

from demoapp.calendar.forms import CalendarModelform


def calendar_view(request):
    form = CalendarModelform()
    if request.method == 'POST':
        form = CalendarModelform(request.POST)
        if form.is_valid():
            form.save()
    return render(request, 'gentelella/index.html', {'form': form})
