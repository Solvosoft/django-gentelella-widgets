from django.contrib import admin

# Register your models here.
from demoapp.models import Country, WithCatalog, Catalog, OneCatalog

admin.site.register(Country)
admin.site.register(Catalog)
admin.site.register(WithCatalog)
admin.site.register(OneCatalog)
