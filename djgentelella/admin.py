from django.contrib import admin

from djgentelella.firmador_digital.models import UserSignatureConfig
from djgentelella.models import MenuItem, Help, GentelellaSettings, Notification, \
    ChunkedUpload, Trash
from djgentelella.models import PermissionsCategoryManagement
from djgentelella.utils import clean_cache
from django.contrib.admin.models import LogEntry
from djgentelella.history.utils import ACTIONS
from django.utils.translation import gettext_lazy as _

class MenuAdmin(admin.ModelAdmin):
    filter_horizontal = ['permission']

class GentelellaSettingsAdmin(admin.ModelAdmin):
    list_display = ['key', 'value']
    search_fields = ['key']
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

class UserSignatureConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'config')

class TrashAdmin(admin.ModelAdmin):
    list_display = ("id", "deleted_by", "content_type", "object_id", "object_repr", "created_at")
    ordering = ("-created_at",)
    search_fields = ("id",)


class ActionFlagFilter(admin.SimpleListFilter):
    title = _("Action")
    parameter_name = "action_flag"

    def lookups(self, request, model_admin):
        return [(k, str(v)) for k, v in ACTIONS.items()]

    def queryset(self, request, queryset):
        val = self.value()
        if not val:
            return queryset
        try:
            return queryset.filter(action_flag=int(val))
        except ValueError:
            return queryset.none()

class LogEntryAdmin(admin.ModelAdmin):
    verbose_name = _("History")
    verbose_name_plural = _("History")
    list_display = ("id", "action_time", "user", "content_type", "object_id", "object_repr", "action_label", "change_message")
    search_fields = ("content_type__app_label", "content_type__model", "object_id", "user__username")
    list_filter = (
        ActionFlagFilter,
    )
    def action_label(self, obj):
        return ACTIONS.get(obj.action_flag, obj.get_action_flag_display() or obj.action_flag)
    action_label.short_description = _("Action")


admin.site.register(UserSignatureConfig, UserSignatureConfigAdmin)
admin.site.register(ChunkedUpload, ChunkedUploadAdmin)
admin.site.register(MenuItem, MenuAdmin)
admin.site.register(Help)
admin.site.register(PermissionsCategoryManagement)
admin.site.register(GentelellaSettings, GentelellaSettingsAdmin)
admin.site.register(Notification, NotificationAdmin)
admin.site.register(Trash, TrashAdmin)
admin.site.register(LogEntry, LogEntryAdmin)
