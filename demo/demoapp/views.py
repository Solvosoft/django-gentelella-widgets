from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from djgentelella.notification import create_notification
from .forms import FooModelForm, FooBasicForm
from .models import Foo
# Create your views here.

@login_required
def create_notification_view(request):
    email = request.GET.get('email', '')
    if email:
        create_notification("This es an example of notification system with email", request.user,
           'success', link='notifications',
            link_prop={'args': [], 'kwargs': {'pk': 2}},
                            request=request, send_email=True)
    else:
        create_notification("This es an example of notification system", request.user,
           'success', link='notifications',
            link_prop={'args': [], 'kwargs': {'pk': 2}}, request=request)

    messages.success(request, 'A notification was created, check the widget')



    return redirect("/")

def formView(request):
    form = FooModelForm()
    if request.method == 'POST':
        form  = FooModelForm(request.POST)
        form.is_valid()
        my_foo = Foo.objects.create(**form.cleaned_data)
        my_foo.save()
    return render(request, 'form.html', {'form': form})
