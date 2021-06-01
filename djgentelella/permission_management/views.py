from django.http import JsonResponse
from django.template.loader import render_to_string
from djgentelella.models import PermissionsCategoryManagement

def get_permission_list(request):

    response ={}
    categories = {}

    q = request.GET.get('q')

    permissions_list = PermissionsCategoryManagement.objects.filter(url_name__in=q.split(',')).\
        values('category', 'permission', 'name')

    for perm in permissions_list:
        if perm['category'] not in categories:

            categories[perm['category']] = []

        categories[perm['category']].append({'id': perm['permission'],
                                             'name': perm['name']})

    response['result'] = render_to_string('gentelella/permission_management/permissionmanagement_list.html', {'categories': categories})
    return JsonResponse(response)