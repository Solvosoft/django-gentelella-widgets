from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy

from demoapp.maps.forms import PlaceForm, SimplePointForm
from demoapp.models import Place


def map_point_view(request):
    form = PlaceForm()
    # Prefixed: both forms have a field called "location", and without it they
    # would render the same id_location twice. The widget registry is keyed by
    # id, so the second map would tear the first one down.
    simple_form = SimplePointForm(prefix='simple')
    if request.method == 'POST':
        form = PlaceForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(reverse('map-point'))
    return render(
        request,
        'maps.html',
        {'form': form, 'simple_form': simple_form, 'places': Place.objects.all()},
    )


def map_dashboard_view(request):
    return render(
        request,
        'djmap.html',
        {
            'places_url': reverse_lazy('placesmap-list'),
            'countries': Place.objects.exclude(country='')
            .values_list('country', flat=True)
            .distinct(),
        },
    )
