from django.contrib import messages
from django.shortcuts import render

from demoapp.calendar.forms import CalendarModelform


def calendar_view(request):
    form = CalendarModelform(initial={'options': '{}'})
    if request.method == 'POST':
        form = CalendarModelform(request.POST, initial={'options': '{}'})
        if form.is_valid():
            form.save()
            messages.success(request, "Form submitted succesfully")
    return render(request, 'gentelella/index.html', {'form': form})
