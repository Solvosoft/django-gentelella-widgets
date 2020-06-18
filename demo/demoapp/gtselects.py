from demoapp.models import Person, Comunity
from djgentelella.groute import register_lookups
from djgentelella.select_view import GModelLookup


@register_lookups(prefix="person", basename="personbasename")
class PersonGModelLookup(GModelLookup):
    model = Person
    fields = ['name']
    #queryset = Person.objects.none()


@register_lookups(prefix="comunity", basename="comunitybasename")
class ComunityGModelLookup(GModelLookup):
    model = Comunity
    fields = ['name']