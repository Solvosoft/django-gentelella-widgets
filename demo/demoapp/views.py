from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Permission
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from djgentelella.notification import create_notification
from .autocomplete.forms import ABCDEModalGroupForm
from .datatables.serializer import PermissionSerializer
from .forms import FooModelForm, YesNoInputAddForm, PersonModalForm
from .models import YesNoInput, PermissionRelation
from .serializers import PermissionRelationSerializer


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


# class PermissionList(generics.RetrieveAPIView):
#     queryset = Permission.objects.all()
#     serializer_class = PermissionSerializer
#     def retrieve(self, request, pk, *args, **kwargs):
#      return super().retrieve(request,  *args, **kwargs)

class PermissionDetail(generics.RetrieveAPIView):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [
        IsAuthenticated]  # Agrega las clases de permisos que necesites

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

class PermissionRelationList(generics.ListCreateAPIView):
    queryset = PermissionRelation.objects.all()
    serializer_class = PermissionRelationSerializer


class RelatedPermissionList(generics.ListAPIView):
    serializer_class = PermissionRelationSerializer

    def get_queryset(self):
        permission_id = self.kwargs['pk']
        # Filtrar los permisos relacionados utilizando la relación en el modelo PermissionRelation
        return PermissionRelation.objects.filter(
            main_permission=permission_id)

