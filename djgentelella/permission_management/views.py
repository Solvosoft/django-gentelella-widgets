import json

from djgentelella.settings import Group, User
from django.http import JsonResponse, Http404
from django.template.loader import render_to_string

from djgentelella.models import PermissionsCategoryManagement
from djgentelella.permission_management.forms import PermCategoryManagementForm


def get_permission_list(request):

    response ={}
    categories = {}

    q = request.GET.get('q')
    if not q:
        raise Http404
    permissions_list = PermissionsCategoryManagement.objects.filter(url_name__in=q.split(',')).\
        values('category', 'permission', 'name')

    for perm in permissions_list:
        if perm['category'] not in categories:

            categories[perm['category']] = []

        categories[perm['category']].append({'id': perm['permission'],
                                             'name': perm['name']})

    response['result'] = render_to_string('gentelella/permission_management/permissionmanagement_list.html', {'categories': categories})
    return JsonResponse(response)



def save_permcategorymanagement(request):

    response = {}

    form = PermCategoryManagementForm(request.POST)

    if form.is_valid():
        pass

    return JsonResponse(response)



def save_permsgroup_user(request):
    response = {'result': False}

    perms = request.POST.getlist('permissions')

    if int(request.POST['option']) == 2:

        group = Group.objects.filter(pk=request.GET['group']).first()

        if group is not None:
            group.permissions.clear()
            for perm in perms:
                group.permissions.add(perm)

        response['result'] = True

    else:

        user = User.objects.filter(pk=request.GET['user']).first()

        if user is not None:
            user.user_permissions.clear()
            for perm in perms:
                user.user_permissions.add(perm)
        response['result'] = True

    return JsonResponse(response)


def get_permissions(request, pk):

    if int(request.GET.get('option')) == 2:
        return get_group_permissions(pk)
    else:
        return get_user_permissions(pk)


def get_group_permissions(pk):
    group = Group.objects.filter(pk=pk).first()
    perms = []
    response = {}

    if group is not None:

        for perm in group.permissions.all():
            perms.append({'id': perm.pk, 'name': perm.name, 'codename': perm.codename})

        response['result'] = perms
    return JsonResponse(response, safe=False)


def get_user_permissions(pk):
    perms = []
    user = User.objects.filter(pk=pk).first()
    response = {}

    if user is not None:

        for perm in user.user_permissions.all():
            perms.append({'id': perm.pk, 'name': perm.name, 'codename': perm.codename})

        response['result'] = perms
        return JsonResponse(response, safe=False)
