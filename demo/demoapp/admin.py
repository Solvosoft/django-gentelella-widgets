from django.contrib import admin

from .models import WithCatalog, Catalog, OneCatalog, Country, Person, Foo, \
    Community, Employee, \
    ChunkedUploadItem, Event, Calendar, DigitalSignature

admin.site.register(DigitalSignature)
admin.site.register(Country)
admin.site.register(Catalog)
admin.site.register(WithCatalog)
admin.site.register(OneCatalog)
admin.site.register(Person)
admin.site.register(Foo)
admin.site.register(Community)
admin.site.register(Employee)
admin.site.register(ChunkedUploadItem)
admin.site.register(Calendar)
admin.site.register(Event)
