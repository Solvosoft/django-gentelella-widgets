from demoapp.models import Person
from djgentelella.groute import register_lookups
from djgentelella.select_view import GModelLookup


@register_lookups(prefix="person", basename="personbasename")
class PersonGModelLookup(GModelLookup):
    model = Person
    fields = ['name']
    #queryset = Person.objects.none()