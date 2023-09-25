from django.contrib import admin

from .models import WithCatalog, Catalog, OneCatalog, Country, Person, Foo, \
    Comunity, Employee, \
    ChunkedUploadItem, Event, Calendar, PeopleGroup, PersonGroup, ChoiceItem


class PeopleGroupAdmin(admin.ModelAdmin):
    filter_horizontal = ['people']

class PersonGroupAdmin(admin.ModelAdmin):
    filter_horizontal = ['persons', 'items']
    #filter_horizontal = ['items']


admin.site.register(PeopleGroup, PeopleGroupAdmin)
admin.site.register(PersonGroup, PersonGroupAdmin)
#admin.site.register(PersonGroup, ChoiceItemGroupAdmin)
admin.site.register(Country)
admin.site.register(Catalog)
admin.site.register(WithCatalog)
admin.site.register(OneCatalog)
admin.site.register(Person)
admin.site.register(ChoiceItem)
admin.site.register(Foo)
admin.site.register(Comunity)
admin.site.register(Employee)
admin.site.register(ChunkedUploadItem)
admin.site.register(Calendar)
admin.site.register(Event)
