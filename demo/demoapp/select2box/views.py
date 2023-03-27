from .forms import dataOptions
from django.views.generic import FormView
class formSelect2BoxView(FormView):
    form_class = dataOptions
    template_name = 'gentelella/index.html'
