from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from .forms import DynamicContactForm, DynamicContactFormSet


@login_required
def dynamic_actions_form(request):
    form = DynamicContactForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, _('Contact saved'))
        return redirect('dynamic_actions_form')
    return render(request, 'dynamic_actions/form.html', {'form': form})


@login_required
def dynamic_actions_formset(request):
    formset = DynamicContactFormSet(request.POST or None, prefix='contacts')
    if request.method == 'POST' and formset.is_valid():
        for form in formset:
            if form.has_changed() and not form.cleaned_data.get('DELETE'):
                form.save()
        messages.success(request, _('Contacts saved'))
        return redirect('dynamic_actions_formset')
    return render(request, 'dynamic_actions/formset.html', {'formset': formset})


@login_required
def dynamic_actions_crud(request):
    return render(request, 'dynamic_actions/crud.html', {
        'create_form': DynamicContactForm(prefix='create'),
        'update_form': DynamicContactForm(prefix='update'),
    })
