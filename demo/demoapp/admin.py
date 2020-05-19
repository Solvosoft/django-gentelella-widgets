from django.contrib import admin

# Register your models here.
from .models import Country, Person, Colors

admin.site.register(Country)
admin.site.register(Person)
admin.site.register(Colors)
