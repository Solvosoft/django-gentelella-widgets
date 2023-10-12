from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from demoapp.models import DateRange
from .forms import DateRangeForms


class CreateDate(CreateView):
    model = DateRange
    form_class = DateRangeForms
    template_name = 'gentelella/date_range/form-date.html'
    success_url = reverse_lazy('date-range-list')


class ListDate(ListView):
    model = DateRange
    template_name = 'gentelella/date_range/list-date.html'

    def get_queryset(self):
        return self.model.objects.all()


class UpdateDate(UpdateView):
    model = DateRange
    form_class = DateRangeForms
    template_name = 'gentelella/date_range/form-date.html'
    success_url = reverse_lazy('date-range-list')

    def form_valid(self, form):
        return super().form_valid(form)
