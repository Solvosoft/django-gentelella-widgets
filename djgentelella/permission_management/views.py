from django.http import JsonResponse
from django.template.loader import render_to_string

from models import PermissionsCategoryManagement


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