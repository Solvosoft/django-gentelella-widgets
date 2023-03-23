from demoapp.models import selectModel
from .forms import dataOptions
from django.views.generic import FormView
class formViewTest(FormView):
    model = selectModel
    form_class = dataOptions
    context_object_name = 'data_pred'
    template_name = 'gentelella/selectmultiple/selectmultiple.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['data_pred'] = selectModel.objects.all()
        return context
