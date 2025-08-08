from django.contrib import admin

from .models import WithCatalog, Catalog, OneCatalog, Country, Person, Foo, \
    Community, Employee, ChunkedUploadItem, Event, \
        Calendar, DigitalSignature, SelectImage, Img, Customer


class DigitalSignatureAdmin(admin.ModelAdmin):
    list_display = ('id', 'filename', 'file_code', 'created', 'updated')


class CustomerAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "email", "phone_number", "is_deleted")
    list_filter = ("is_deleted",)

    def get_queryset(self, request):
        # important to define for see deleted
        return Customer.objects_with_deleted.all()

admin.site.register(DigitalSignature, DigitalSignatureAdmin)
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
admin.site.register(SelectImage)
admin.site.register(Img)
admin.site.register(Customer, CustomerAdmin)
