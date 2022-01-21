from django import forms
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.timezone import now
from rest_framework import serializers

from demoapp.models import Event, Calendar
from djgentelella.forms.forms import CustomForm
from djgentelella.widgets import core as genwidgets
from djgentelella.widgets import numberknobinput as knobwidget
from djgentelella.widgets.calendar import CalendarInput
from djgentelella.widgets.files import FileChunkedUpload
from djgentelella.widgets.timeline import UrlTimeLineInput


class ExampleForm(CustomForm):

    calendar = forms.CharField(
        widget=CalendarInput(
            calendar_attrs={'initialView': 'timeGridWeek'},
            events=Event.objects.all()
        )
    )

    calendar2 = forms.CharField(
        widget=CalendarInput(
            calendar_attrs={},
            events=Event.objects.all()
        )
    )


def home(request):
    form = ExampleForm()
    if request.method == 'POST':
        form = ExampleForm(request.POST)
        if form.is_valid():
            print(form.cleaned_data['events'])
    return render(request, 'gentelella/index.html', {'form': form})


@login_required
def logeado(request):
    return HttpResponse("Wiii")


def add_view_select(request):
    if request.method == 'POST':
        return JsonResponse({'ok': True, 'id': 2, 'text': 'Data example'})
        return JsonResponse({'ok': False,
                             'title': "Esto no dice nada",
                             'message': 'Esto es un errror'})
    data = {
        'ok':  True,
        'title': 'Formulario de ejemplo',
        'message': """
        <form method="post" action="/add_view_select">
            <textarea name="description" > </textarea>
            <input type="text" name="name" />
            <select name="bingo">
               <option value="Nada">Nada</option><option value="otro">Otro</option>
            </select>
        </form>
        """
    }
    return JsonResponse(data)


def get_events(request):
    events = Event.objects.all()
    events_json = serializers.serialize('json', events)
    return HttpResponse(events_json, content_type='application/json')