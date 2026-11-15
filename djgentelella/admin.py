from django import forms
from django.apps import apps
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from djgentelella.authorization import (
    FLAG_NAME,
    flag_names,
    flag_value,
    set_flag,
    validate_condition,
)
from djgentelella.firmador_digital.models import UserSignatureConfig
from djgentelella.models import (
    MenuItem,
    Help,
    GentelellaSettings,
    Notification,
    ChunkedUpload,
    Trash,
    HistoryRelation,
    TrashRelation,
)
from djgentelella.models import PermissionsCategoryManagement
from djgentelella.sites import sites_installed
from djgentelella.utils import clean_cache
from django.contrib.admin.models import LogEntry
from djgentelella.history.utils import ACTIONS
from django.utils.translation import gettext_lazy as _


# The Site of menus and settings is optional (empty = global); the column and
# the filter only make sense when django.contrib.sites is there.
SITE_COLUMNS = ['site'] if sites_installed() else []


class MenuItemForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = '__all__'

    def clean_condition(self):
        # An unknown authorization is an error here, and only False (and a
        # log) when the menu is rendered.
        condition = self.cleaned_data.get('condition')
        errors = validate_condition(condition, '$.condition')
        if errors:
            raise forms.ValidationError([str(error) for error in errors])
        return condition


class MenuAdmin(admin.ModelAdmin):
    form = MenuItemForm
    filter_horizontal = ['permission']
    list_display = ['__str__'] + SITE_COLUMNS
    list_filter = SITE_COLUMNS


#: The states a flag can be given in one scope from the flags page.
FLAG_STATES = {'on': True, 'off': False, 'inherit': None}


class GentelellaSettingsAdmin(admin.ModelAdmin):
    list_display = ['key', 'value'] + SITE_COLUMNS
    list_filter = SITE_COLUMNS
    search_fields = ['key']
    list_editable = ['value']
    actions = ['clean_settings_cache']
    change_list_template = 'admin/djgentelella/gentelellasettings/change_list.html'

    def clean_settings_cache(self, request, queryset):
        for key, site_id in queryset.values_list('key', 'site_id'):
            clean_cache([key], site=site_id)

    clean_settings_cache.short_description = 'Clean settings cache'

    def get_urls(self):
        return [
            path('flags/', self.admin_site.admin_view(self.flags_view),
                 name='djgentelella_feature_flags'),
        ] + super().get_urls()

    def flags_view(self, request):
        """Feature flags: one row per flag, one toggle per
        scope -- global and each Site, which may also inherit the global."""
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        sites = list(apps.get_model('sites', 'Site').objects.order_by('domain')) \
            if sites_installed() else []
        if request.method == 'POST':
            if not self.has_change_permission(request):
                raise PermissionDenied
            self._save_flag(request, sites)
            return redirect(reverse('admin:djgentelella_feature_flags'))
        rows = []
        for name in flag_names():
            global_value = flag_value(name)
            cells = [{'site': None, 'stored': global_value,
                      'effective': bool(global_value)}]
            for site in sites:
                stored = flag_value(name, site)
                cells.append({'site': site, 'stored': stored,
                              'effective': bool(global_value if stored is None
                                                else stored)})
            rows.append({'name': name, 'cells': cells})
        context = {
            **self.admin_site.each_context(request),
            'title': _('Feature flags'),
            'opts': self.model._meta,
            'sites': sites,
            'rows': rows,
            'can_change': self.has_change_permission(request),
        }
        return TemplateResponse(
            request, 'admin/djgentelella/gentelellasettings/flags.html', context)

    def _save_flag(self, request, sites):
        name = request.POST.get('name', '').strip()
        state = request.POST.get('state', '')
        site_id = request.POST.get('site', '')
        if not FLAG_NAME.match(name):
            messages.error(request, _('Invalid flag name.'))
            return
        if state not in FLAG_STATES:
            messages.error(request, _('Invalid flag state.'))
            return
        site = None
        if site_id:
            site = next((s for s in sites if str(s.pk) == site_id), None)
            if site is None:
                messages.error(request, _('Unknown site.'))
                return
        elif state == 'inherit':
            # The global value has nothing to inherit from: it is turned off.
            state = 'off'
        set_flag(name, FLAG_STATES[state], site=site)
        messages.success(request, _('Flag %(name)s updated.') % {'name': name})


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
    list_display = (
        'id',
        'deleted_by',
        'content_type',
        'object_id',
        'object_repr',
        'created_at',
    )
    ordering = ('-created_at',)
    search_fields = ('id',)


class ActionFlagFilter(admin.SimpleListFilter):
    title = _('Action')
    parameter_name = 'action_flag'

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
    verbose_name = _('History')
    verbose_name_plural = _('History')
    list_display = (
        'id',
        'action_time',
        'user',
        'content_type',
        'object_id',
        'object_repr',
        'action_label',
        'change_message',
    )
    search_fields = (
        'content_type__app_label',
        'content_type__model',
        'object_id',
        'user__username',
    )
    list_filter = (ActionFlagFilter,)

    def action_label(self, obj):
        return ACTIONS.get(
            obj.action_flag, obj.get_action_flag_display() or obj.action_flag
        )

    action_label.short_description = _('Action')


class HistoryRelationAdmin(admin.ModelAdmin):
    list_display = ('id', 'log_entry', 'content_type', 'object_id', 'data')
    list_filter = ('content_type',)
    search_fields = ('object_id',)
    raw_id_fields = ('log_entry',)


class TrashRelationAdmin(admin.ModelAdmin):
    list_display = ('id', 'trash', 'content_type', 'object_id')
    list_filter = ('content_type',)
    search_fields = ('object_id',)
    raw_id_fields = ('trash',)


admin.site.register(UserSignatureConfig, UserSignatureConfigAdmin)
admin.site.register(ChunkedUpload, ChunkedUploadAdmin)
admin.site.register(MenuItem, MenuAdmin)
admin.site.register(Help)
admin.site.register(PermissionsCategoryManagement)
admin.site.register(GentelellaSettings, GentelellaSettingsAdmin)
admin.site.register(Notification, NotificationAdmin)
admin.site.register(Trash, TrashAdmin)
admin.site.register(LogEntry, LogEntryAdmin)
admin.site.register(HistoryRelation, HistoryRelationAdmin)
admin.site.register(TrashRelation, TrashRelationAdmin)
