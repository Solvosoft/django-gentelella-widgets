import json

from django.contrib.auth.models import Permission

from djgentelella.settings import Group, User
from django.http import JsonResponse, Http404
from django.template.loader import render_to_string

from djgentelella.models import PermissionsCategoryManagement
from djgentelella.permission_management.forms import PermCategoryManagementForm



def get_permission_list(request):

    response = {}
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


def management_permissions(item, item_type, permissions, permission_list):

    if item_type == 1:

        for perm in permission_list:
            if perm in item.user_permissions.all() and not perm in permissions:
                item.user_permissions.remove(perm)
            elif not perm in item.user_permissions.all() and perm in permissions:
                item.user_permissions.add(perm)
    else:
        for perm in permission_list:
            if perm in item.permissions.all() and not perm in permissions:
                item.permissions.remove(perm)
            elif not perm in item.permissions.all() and perm in permissions:
                item.permissions.add(perm)


def save_permcategorymanagement(request):

    response = {'result': 'error'}
    urlname = request.GET.get('urlname', '')
    form = PermCategoryManagementForm(request.POST)

    if urlname:

        permissions_pk = list(PermissionsCategoryManagement.objects.filter(url_name__in=urlname.split(',')).values_list('permission', flat=True))
        permissions_list = Permission.objects.filter(pk__in=permissions_pk)

        if request.user.is_superuser:

            if form.is_valid():

                item_type = int(form.cleaned_data['type'])
                user = form.cleaned_data['user']
                group = form.cleaned_data['group']
                permissions = form.cleaned_data['permissions']
                print(request.POST)
                print(permissions)

                if item_type:
                    if item_type == 1:
                        management_permissions(user, item_type, permissions, permissions_list)
                    else:
                        management_permissions(group, item_type, permissions, permissions_list)
                    response['result'] = 'ok'
            else:
                response['message'] = 'Form data has errors, please try again'
                response['errors'] = form.errors
        else:
            response['message'] = "User isn't a super user"
    else:
        response['message'] = "Permissions don't exists"

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
    q = request.GET.get('q')

    if not q:
        raise Http404
    permission_list = PermissionsCategoryManagement.objects.filter(url_name__in=q.split(',')). \
        values('category', 'permission', 'name')

    if int(request.GET.get('option')) == 2:
        return get_group_permissions(pk,permission_list)
    else:
        return get_user_permissions(pk,permission_list)


def check_permissions(perm_list, perm_item):
    result = False
    for perm in perm_list:
        if perm['permission'] == perm_item.pk:
            return True
    return result


def get_group_permissions(pk,permission_list):
    group = Group.objects.filter(pk=pk).first()
    perms = []
    response = {}
    if group is not None:

        for perm in group.permissions.all():
            if check_permissions(permission_list,perm):
                perms.append({'id': perm.pk, 'name': perm.name, 'codename': perm.codename})

        response['result'] = perms
    return JsonResponse(response)



def get_user_permissions(pk,permission_list):
    perms = []
    user = User.objects.filter(pk=pk).first()
    response = {}

    if user is not None:

        for perm in user.user_permissions.all():
            if check_permissions(permission_list, perm):
                perms.append({'id': perm.pk, 'name': perm.name, 'codename': perm.codename})

        response['result'] = perms

        return JsonResponse(response)

