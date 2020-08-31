from django.shortcuts import render
from django.urls import reverse_lazy
from .forms import InputMaskForms, InputMaskFormsClone
from demoapp.models import InputMask
from datetime import datetime

from django.views.generic import CreateView, ListView, UpdateView


class InsertMask(CreateView):
    model = InputMask
    form_class = InputMaskForms
    template_name = 'gentelella/input_mask/inputs.html'
    success_url = reverse_lazy('input-mask-list')

    def form_valid(self, form):
        self.object = form.save(commit=False)
        phone = self.request.POST.getlist('phone')
        self.object.phone=phone[0]
        card=self.object.credit_card.split('_')
        self.object.credit_card=card[0]
        self.object.save()
        return super().form_valid(form)
    
    def add_forms(self, request):
        return render(request, self.template_name, {'form': self.form_class, 'forms': InputMaskFormsClone})

    def get(self, request, *args, **kwargs):
        return self.add_forms(request)


class listMask(ListView):
    model = InputMask
    template_name = 'gentelella/input_mask/view_inputs.html'


class EditMask(UpdateView):
    model = InputMask
    form_class = InputMaskForms
    template_name = 'gentelella/input_mask/inputs.html'
    success_url = reverse_lazy('input-mask-list')
    def form_valid(self, form):
        self.object = form.save(commit=False)
        card=self.object.credit_card.split('_')
        self.object.credit_card=card[0]
        self.object.save()
        return super().form_valid(form)
