from django.contrib import admin

from djgentelella.models import MenuItem, Help, GentelellaSettings, Notification, ChunkedUpload
from djgentelella.utils import clean_cache
from djgentelella.models import PermissionsCategoryManagement


class MenuAdmin(admin.ModelAdmin):
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



class ChunkedUploadAdmin(admin.ModelAdmin):
    list_display = ('upload_id', 'filename', 'status', 'created_on')
    search_fields = ('filename', 'filename')
    list_filter = ('status',)



admin.site.register(ChunkedUpload, ChunkedUploadAdmin)
admin.site.register(MenuItem, MenuAdmin)
admin.site.register(Help)
admin.site.register(PermissionsCategoryManagement)
admin.site.register(GentelellaSettings, GentelellaSettingsAdmin)
admin.site.register(Notification, NotificationAdmin)

