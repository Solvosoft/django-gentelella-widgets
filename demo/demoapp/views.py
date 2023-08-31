from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Permission
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView
from rest_framework import generics

from djgentelella.notification import create_notification
from .autocomplete.forms import ABCDEModalGroupForm
from .forms import FooModelForm, YesNoInputAddForm, PersonModalForm
from .models import YesNoInput

@login_required
def create_notification_view(request):
    email = request.GET.get('email', '')
    if email:
        create_notification("This es an example of notification system with email",
                            request.user,
                            'success', link='notifications',
                            link_prop={'args': [], 'kwargs': {'pk': 2}},
                            request=request, send_email=True)
    else:
        create_notification("This es an example of notification system", request.user,
                            'success', link='notifications',
                            link_prop={'args': [], 'kwargs': {'pk': 2}},
                            request=request)

    messages.success(request, 'A notification was created, check the widget')

    return redirect("/")


def knobView(request):
    form = FooModelForm()
    if request.method == 'POST':
        form = FooModelForm(request.POST)
        if form.is_valid():
            form.save()
            form = FooModelForm()

    return render(request, 'knobs-form.html', {'form': form})


class YesNoInputView(CreateView):
    model = YesNoInput
    form_class = YesNoInputAddForm
    template_name = 'yesnoinput.html'
    success_url = reverse_lazy('yes-no-input-add')


def bt_modal_display(request):
    context = {
        'form': PersonModalForm(),
        'abcdeform': ABCDEModalGroupForm()
    }
    return render(request, 'btmodals.html', context=context)


