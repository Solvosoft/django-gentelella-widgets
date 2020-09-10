from django.urls import reverse_lazy
from .forms import gridSliderForm
from demoapp.models import gridSlider
from django.views.generic import CreateView, ListView, UpdateView


class AddGrid(CreateView):
    model = gridSlider
    form_class = gridSliderForm
    template_name = 'gentelella/grid_slider/form-grid.html'
    success_url = reverse_lazy('grid-slider-add')
    
    def form_valid(self, form):
        print(self.request.POST)
        return super().form_valid(form)
