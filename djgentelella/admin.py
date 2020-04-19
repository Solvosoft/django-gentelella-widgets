from django.contrib import admin

# Register your models here.
from mptt.admin import DraggableMPTTAdmin

from djgentelella.models import MenuItem, Help, GentelellaSettings


class MenuAdmin(DraggableMPTTAdmin):
    filter_horizontal = ['permission']
admin.site.register(MenuItem, MenuAdmin)
admin.site.register(Help)
admin.site.register(GentelellaSettings)