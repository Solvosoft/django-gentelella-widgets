from django.urls import reverse_lazy
from .forms import InputMaskForms
from demoapp.models import InputMask

from django.views.generic import CreateView


class InsertMask(CreateView):
    model=InputMask
    form_class=InputMaskForms
    template_name='gentelella/input_mask/inputs.html'
    success_url=reverse_lazy('inputs_mask_view')
    
    
    
