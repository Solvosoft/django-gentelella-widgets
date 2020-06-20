from demoapp.models import Person, Comunity, Country
from djgentelella.groute import register_lookups
from djgentelella.select_view import BaseSelect2View


@register_lookups(prefix="person", basename="personbasename")
class PersonGModelLookup(BaseSelect2View):
    model = Person
    fields = ['name']
    #queryset = Person.objects.none()


@register_lookups(prefix="comunity", basename="comunitybasename")
class ComunityGModelLookup(BaseSelect2View):
    model = Comunity
    fields = ['name']

@register_lookups(prefix="country", basename="countrybasename")
class CountryGModelLookup(BaseSelect2View):
    model = Country
    fields = ['name']
