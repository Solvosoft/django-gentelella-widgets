import json

from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views.decorators.csrf import requires_csrf_token, ensure_csrf_cookie, \
    csrf_exempt

from .forms import dataOptions, PeopleSelect2BoxForm
from django.views.generic import FormView, CreateView, UpdateView, ListView

from ..forms import PersonForm, CityForm
from ..models import PeopleGroup


class formSelect2BoxView(FormView):
    form_class = dataOptions
    template_name = 'gentelella/index.html'

class Select2BoxGroupAdd(CreateView):
    model = PeopleGroup
    success_url = reverse_lazy('select2box-group-list')
    form_class = PeopleSelect2BoxForm
    template_name = 'gentelella/index.html'


class Select2BoxGroupChange(UpdateView):
    model = PeopleGroup
    success_url = reverse_lazy('select2box-group-list')
    form_class = PeopleSelect2BoxForm
    template_name = 'gentelella/index.html'


class Select2BoxGroupList(ListView):
    model = PeopleGroup
    template_name = 'people_group_select2box.html'

def Select2BoxPersonAddView(request):
    form_t = PersonForm(prefix='person_new_data')
    if request.method == "GET":
        render_str = render_to_string('gentelella/widgets/select2box_modal_body.html', {'form': form_t})
        return JsonResponse({'result': render_str})

    elif request.method == "POST":
        json_data = json.loads(request.body)
        review_data = PersonForm(json_data, prefix='person_new_data')
        if review_data.is_valid():
            try:
                saved_data = review_data.save()
                return JsonResponse({'result': {'id': saved_data.id,
                                                'text': saved_data.name,
                                                'selected': False, 'disabled': False}})
            except (KeyError, PersonForm.errors):
                return JsonResponse({'error': 'Error'})
        else:
            return JsonResponse({'error':'Data Invalid'})

def Select2BoxComunityAddView(request):
    form_t = CityForm()
    if request.method == "GET":
        render_str = render_to_string('gentelella/widgets/select2box_modal_body.html', {'form': form_t})
        return JsonResponse({'result': render_str})

    elif request.method == "POST":
        test_yy = json.loads(request.body)
        review_data = CityForm(test_yy)
        if review_data.is_valid():
            try:
                saved_data = review_data.save()
                return JsonResponse({'result': {'id':saved_data.id, 'text':saved_data.name, 'selected':False, 'disabled': False}})
            except (KeyError, CityForm.errors):
                return JsonResponse({'error': 'Error'})
        else:
            return JsonResponse({'error':'Data Invalid'})
