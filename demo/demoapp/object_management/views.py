from django.shortcuts import render

from demoapp.forms import ObjectManagementForm


def object_management(request):
    context = {
        'create_form': ObjectManagementForm(prefix='create'),
        'update_form': ObjectManagementForm(prefix='update'),
    }
    return render(request, 'object_management.html', context=context)
