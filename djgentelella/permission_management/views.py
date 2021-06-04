from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, Http404
from django.template.loader import render_to_string

from djgentelella.permission_management.forms import PermCategoryManagementForm, FilterPermCategoryForm
from djgentelella.permission_management.objinterface import ObjManager
from djgentelella.settings import Group, User


@login_required
@user_passes_test(lambda u: u.is_superuser )
def get_permission_list(request):
    response = {}
    form = FilterPermCategoryForm(request.GET)
    if form.is_valid():
        instance = ObjManager.get_class(request, form)
        categories=instance.get_permission_list()
        response['result'] = render_to_string('gentelella/permission_management/permissionmanagement_list.html', {'categories': categories})
        return JsonResponse(response)
    else:
        response['message'] = 'Form data has errors, please try again'
        response['errors'] = form.errors
    return JsonResponse(response)


@login_required
@user_passes_test(lambda u: u.is_superuser )
def save_permcategorymanagement(request):
    response = {'result': 'error'}
    form = PermCategoryManagementForm(request.POST)
    if form.is_valid():
        instance = ObjManager.get_class(request, form)
        instance.update_permission()
        response['result'] = 'ok'
    else:
        response['message'] = 'Form data has errors, please try again'
        response['errors'] = form.errors
    return JsonResponse(response)


@login_required
@user_passes_test(lambda u: u.is_superuser )
def get_permissions(request, pk):
    form = FilterPermCategoryForm(request.GET)
    response = {}
    if form.is_valid():

        instance = ObjManager.get_class(request, form)
        try:
            response = {'result':  instance.get_django_permissions(pk=pk)}
        except User.DoesNotExist or Group.DoesNotExist:
            raise Http404
    else:
        response['message'] = 'Form data has errors, please try again'
        response['errors'] = form.errors
    return JsonResponse(response)