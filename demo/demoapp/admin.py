from django.contrib import admin
from .models import WithCatalog, Catalog, OneCatalog, Country, Person, Colors, Foo, Comunity, Employee,ChunkedUploadItem

admin.site.register(Country)
admin.site.register(Catalog)
admin.site.register(WithCatalog)
admin.site.register(OneCatalog)
admin.site.register(Person)
admin.site.register(Colors)
admin.site.register(Foo)
admin.site.register(Comunity)
admin.site.register(Employee)
admin.site.register(ChunkedUploadItem)