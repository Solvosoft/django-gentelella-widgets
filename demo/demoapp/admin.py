from django.contrib import admin

from .models import WithCatalog, Catalog, OneCatalog, Country, Person, Foo, \
    Comunity, Employee, \
    ChunkedUploadItem, Event, Calendar, PeopleGroup


class PeopleGroupAdmin(admin.ModelAdmin):
    filter_horizontal = ['people']

admin.site.register(PeopleGroup, PeopleGroupAdmin)
admin.site.register(Country)
admin.site.register(Catalog)
admin.site.register(WithCatalog)
admin.site.register(OneCatalog)
admin.site.register(Person)
admin.site.register(Foo)
admin.site.register(Comunity)
admin.site.register(Employee)
admin.site.register(ChunkedUploadItem)
admin.site.register(Calendar)
admin.site.register(Event)
