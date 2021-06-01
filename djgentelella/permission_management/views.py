from django.http import JsonResponse
from django.template.loader import render_to_string
from django.contrib.auth.models import Group, User
from djgentelella.models import PermissionsCategoryManagement


def get_permission_list(request):

    response ={}
    categories = {}

    permissions_list = PermissionsCategoryManagement.objects.filter(url_name__in=request.GET.get('q').split(',')).\
        values('category', 'permission', 'name')

    for perm in permissions_list:
        if perm['category'] not in categories:

            categories[perm['category']] = []

        categories[perm['category']].append({'id': perm['permission'],
                                             'name': perm['name']})

    response['result'] = render_to_string('permissionmanagement_list.html', {'categories': categories})
    return JsonResponse(response)


def get_groups(request):

    group = ''

    user = ''

    response = {}

    perms = request.POST.getlist('permissions')

    if request.POST['option'] == 2:

        group = Group.objects.filter(pk=request.GET['group']).first()

        if group is not None:
            group.permissions.clear()
            for perm in perms:
                group.permissions.add(perm)

        response['result']=group
    else:
        user = User.objects.filter(pk=request.GET['user']).first()

        if user is not None:
            user.permissions.clear()
            for perm in perms:
                user.permissions.add(perm)
        response['result'] = user

    return JsonResponse(response)
