from django.contrib import admin

# Register your models here.
from mptt.admin import DraggableMPTTAdmin

from djgentelella.models import MenuItem, Help

class MenuAdmin(DraggableMPTTAdmin):
    filter_horizontal = ['permission']
admin.site.register(MenuItem, MenuAdmin)
admin.site.register(Help)