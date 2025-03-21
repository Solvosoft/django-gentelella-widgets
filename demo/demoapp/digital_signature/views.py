"""
    This view requires an authenticated user session (enforced by the
    @login_required decorator) to ensure only authorized users can access
    the digital signature functionality.

    Usage notes:
    - Make sure 'DigitalSignatureForm' is defined in 'forms.py' and correctly
      includes the digital signature widget fields.
    - Add a corresponding URL pattern to 'urls.py',
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.forms import modelformset_factory
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, UpdateView, ListView

from djgentelella.forms.forms import GTBaseModelFormSet
from . import forms
from .. import models


@method_decorator(login_required, name='dispatch')
class DigitalSignatureAdd(CreateView):
    model = models.DigitalSignature
    success_url = reverse_lazy('digitalsignature-list')
    form_class = forms.DigitalSignatureAddForm
    template_name = 'gentelella/index.html'

    def get_context_data(self, **kwargs):
        messages.info(self.request,
                      "You can sign your document on edit view, just upload some files")
        return super().get_context_data(**kwargs)


@method_decorator(login_required, name='dispatch')
class DigitalSignatureChange(UpdateView):
    model = models.DigitalSignature
    success_url = reverse_lazy('digitalsignature-list')
    form_class = forms.DigitalSignatureForm
    template_name = 'gentelella/digital_signature/digital_signature.html'


@method_decorator(login_required, name='dispatch')
class DigitalSignatureList(ListView):
    model = models.DigitalSignature
    template_name = 'digital_signature_list.html'

    def get_context_data(self, **kwargs):
        messages.info(self.request,
                      "You can sign your document on edit view, just upload some files")
        return super().get_context_data(**kwargs)


@login_required
def digital_signature_formset(request):
    formset = modelformset_factory(models.DigitalSignature,
                                   form=forms.DigitalSignatureForm,
                                   formset=GTBaseModelFormSet,
                                   can_delete=False,
                                   extra=0)

    valid = True
    if request.method == 'POST':
        fset = formset(request.POST, queryset=models.DigitalSignature.objects.all(),
                       prefix='pff')
        valid = fset.is_valid()
        if valid:
            r = fset.save()
            messages.success(request, "Formset saved successfully")
    if valid:
        fset = formset(queryset=models.DigitalSignature.objects.all(), prefix='pff')

    return render(request, 'modelformset.html', {'formset': fset})
