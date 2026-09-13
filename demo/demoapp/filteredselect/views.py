from django.shortcuts import redirect, render
from django.urls import reverse

from demoapp.filteredselect.forms import PeopleGroupFilteredForm, StaticChoicesForm
from demoapp.models import PeopleGroup


def filtered_select_view(request):
    form = PeopleGroupFilteredForm()
    # Prefixed so the two widgets on the page never share an id: the widget
    # registry is keyed by the id of the real select, and the second one would
    # tear the first one down.
    static_form = StaticChoicesForm(prefix='static')
    if request.method == 'POST':
        form = PeopleGroupFilteredForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(reverse('filteredselect'))
    return render(
        request,
        'filteredselect.html',
        {
            'form': form,
            'static_form': static_form,
            'groups': PeopleGroup.objects.all().prefetch_related('people'),
        },
    )
