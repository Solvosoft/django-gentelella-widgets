from demoapp import models
from djgentelella.groute import register_lookups
from djgentelella.views.select2autocomplete import BaseSelect2View, BaseSelectImg2View


@register_lookups(prefix="person", basename="personbasename")
class PersonGModelLookup(BaseSelect2View):
    model = models.Person
    fields = ['name']
    selected = ['1']

    def get_disabled_display(self, obj):
        return obj.pk == 5


@register_lookups(prefix="community", basename="communitybasename")
class CommunityGModelLookup(BaseSelect2View):
    model = models.Community
    fields = ['name']


@register_lookups(prefix="country", basename="countrybasename")
class CountryGModelLookup(BaseSelect2View):
    model = models.Country
    fields = ['name']


@register_lookups(prefix="a", basename="a")
class ALookup(BaseSelect2View):
    model = models.A
    fields = ['display']


@register_lookups(prefix="b", basename="b")
class BLookup(BaseSelect2View):
    model = models.B
    fields = ['display']
    ref_field = 'a'


@register_lookups(prefix="c", basename="c")
class CLookup(BaseSelect2View):
    model = models.C
    fields = ['display']
    ref_field = 'b'


@register_lookups(prefix="d", basename="d")
class DLookup(BaseSelect2View):
    model = models.D
    fields = ['display']
    ref_field = 'c'


@register_lookups(prefix="e", basename="e")
class ELookup(BaseSelect2View):
    model = models.E
    fields = ['display']
    ref_field = 'd'


@register_lookups(prefix="selectimg", basename="imagebasename")
class ImageSelect2Lookup(BaseSelectImg2View):
    model = models.SelectImage
    fields = ['name']

    def get_url(self, obj):
        return obj.img.url
