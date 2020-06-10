from demoapp.models import Country
from djgentelella.groute import register_lookups
from djgentelella.select_view import GModelLookup


@register_lookups(prefix="hola", basename="luisza")
class PersonGModelLookup(GModelLookup):
    model = Country
    fields = ['pk', 'name']
    #queryset = Person.objects.none()