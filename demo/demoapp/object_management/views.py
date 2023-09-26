from django.shortcuts import render

from demoapp.forms import PersonForm


def person_object_management(response):
    context = {
        'create_form': PersonForm(prefix='create'),
        'update_form': PersonForm(prefix='update'),
    }
    return render(response, 'object_management.html', context=context)

