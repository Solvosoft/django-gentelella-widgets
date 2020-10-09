from django.contrib import admin

# Register your models here.
from mptt.admin import DraggableMPTTAdmin
from djgentelella.models import MenuItem, Help, GentelellaSettings, Notification
from djgentelella.utils import clean_cache


class MenuAdmin(DraggableMPTTAdmin):
    filter_horizontal = ['permission']


class GentelellaSettingsAdmin(admin.ModelAdmin):
    list_display = ['key', 'value']
    search_fields =  ['key']
    list_editable = ['value']
    actions = ['clean_settings_cache']

    def clean_settings_cache(self, request, queryset):
        clean_cache(queryset.values_list('key', flat=True))
    clean_settings_cache.short_description = "Clean settings cache"



class NotificationAdmin(admin.ModelAdmin):
    list_display = ['description', 'state', 'message_type']
    list_editable = ['state']

admin.site.register(MenuItem, MenuAdmin)
admin.site.register(Help)
admin.site.register(GentelellaSettings, GentelellaSettingsAdmin)
admin.site.register(Notification, NotificationAdmin)
