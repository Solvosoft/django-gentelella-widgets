from django.contrib import admin

# Register your models here.
from mptt.admin import DraggableMPTTAdmin
from djgentelella.models import MenuItem, Help, GentelellaSettings, Notification


class MenuAdmin(DraggableMPTTAdmin):
    filter_horizontal = ['permission']

class GentelellaSettingsAdmin(admin.ModelAdmin):
    list_display = ['key', 'value']
    search_fields =  ['key']
    list_editable = ['value']

class NotificationAdmin(admin.ModelAdmin):
    list_display = ['description', 'state', 'message_type']
    list_editable = ['state']

admin.site.register(MenuItem, MenuAdmin)
admin.site.register(Help)
admin.site.register(GentelellaSettings, GentelellaSettingsAdmin)
admin.site.register(Notification, NotificationAdmin)
