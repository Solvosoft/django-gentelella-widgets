from django.shortcuts import get_object_or_404, render

from demoapp.forms import ObjectManagementForm, ObjectManagementNoteForm
from demoapp.models import ObjectManagerDemoModel


def object_management(request):
    context = {
        'create_form': ObjectManagementForm(prefix='create'),
        'update_form': ObjectManagementForm(prefix='update'),
    }
    return render(request, 'object_management.html', context=context)


def object_management_inline(request, pk):
    """Manage the notes of one ObjectManagerDemoModel (inline CRUDAL)."""
    context = {
        'parent': get_object_or_404(ObjectManagerDemoModel, pk=pk),
        'create_form': ObjectManagementNoteForm(prefix='create'),
        'update_form': ObjectManagementNoteForm(prefix='update'),
    }
    return render(request, 'object_management_inline.html', context=context)
