from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView

from djgentelella.notification import create_notification
from .autocomplete.forms import ABCDEModalGroupForm
from .forms import FooModelForm, YesNoInputAddForm, PersonModalForm
from .models import YesNoInput


@login_required
def create_notification_view(request):
    email = request.GET.get('email', '')
    if email:
        create_notification('This es an example of notification system with email',
                            request.user,
                            'success', link='notifications',
                            link_prop={'args': [], 'kwargs': {'pk': 2}},
                            request=request, send_email=True)
    else:
        create_notification('This es an example of notification system', request.user,
                            'success', link='notifications',
                            link_prop={'args': [], 'kwargs': {'pk': 2}},
                            request=request)

    messages.success(request, 'A notification was created, check the widget')

    return redirect('/')


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


# Icon references. None take a context: every page reads its own set from what
# the browser already loaded -- friconix's `paths` global, the CSS rules Font
# Awesome and MDI declare, the <symbol> elements in the flags sprite -- so a
# grid can never drift from the version loaddevstatic downloaded.
def friconix_icons(request):
    return render(request, 'icons/friconix.html')


def mdi_icons(request):
    return render(request, 'icons/mdi.html')


def fontawesome_icons(request):
    return render(request, 'icons/fontawesome.html')


def flag_icons(request):
    return render(request, 'icons/flags.html')
