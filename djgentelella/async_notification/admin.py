from django.contrib import admin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from djgentelella.async_notification.models import (
    EmailTemplate, EmailNotification, AttachedFile,
    NewsLetterTemplate, NewsLetter, NewsLetterTask
)
from djgentelella.async_notification.sending import (
    do_send_notification, do_send_newsletter
)


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('code', 'subject', 'base_template', 'created_at')
    search_fields = ('code', 'subject')
    list_filter = ('created_at',)


@admin.register(EmailNotification)
class EmailNotificationAdmin(admin.ModelAdmin):
    list_display = ('subject', 'status', 'sent', 'enqueued',
                    'retry_count', 'created_at')
    search_fields = ('subject',)
    list_filter = ('status', 'enqueued', 'created_at')
    readonly_fields = ('recipients_raw', 'error_message', 'retry_count',
                       'last_attempt')
    actions = ['send_now']

    @admin.action(description=_('Send selected emails now'))
    def send_now(self, request, queryset):
        sent = 0
        for notification in queryset:
            do_send_notification(notification.pk)
            notification.refresh_from_db()
            if notification.status == 'sent':
                sent += 1
        self.message_user(
            request, _('%(n)d email(s) sent.') % {'n': sent})


@admin.register(AttachedFile)
class AttachedFileAdmin(admin.ModelAdmin):
    list_display = ('file', 'content_type', 'object_id',
                    'is_inline', 'created_at')
    list_filter = ('is_inline', 'content_type')


@admin.register(NewsLetterTemplate)
class NewsLetterTemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'model_base', 'base_template',
                    'created_at')
    search_fields = ('title', 'slug')
    prepopulated_fields = {'slug': ('title',)}


class NewsLetterTaskInline(admin.TabularInline):
    model = NewsLetterTask
    extra = 1
    fields = ('send_date', 'status', 'celery_task_id')
    readonly_fields = ('status', 'celery_task_id')


@admin.register(NewsLetter)
class NewsLetterAdmin(admin.ModelAdmin):
    list_display = ('subject', 'template', 'created_by', 'created_at')
    search_fields = ('subject',)
    list_filter = ('created_at',)
    inlines = [NewsLetterTaskInline]
    actions = ['send_now']
    fieldsets = (
        (None, {
            'fields': ('template', 'subject', 'message', 'base_template',
                       'attached_file'),
        }),
        (_('Recipients'), {
            'classes': ('collapse',),
            'fields': ('recipients', 'bcc', 'cc', 'filters_querystring'),
        }),
    )

    @admin.action(description=_('Send selected newsletters now'))
    def send_now(self, request, queryset):
        sent = 0
        for newsletter in queryset:
            task = NewsLetterTask.objects.create(
                newsletter=newsletter, send_date=timezone.now(),
                status='pending')
            do_send_newsletter(task.pk)
            task.refresh_from_db()
            if task.status == 'sent':
                sent += 1
        self.message_user(
            request, _('%(n)d newsletter(s) sent.') % {'n': sent})


@admin.register(NewsLetterTask)
class NewsLetterTaskAdmin(admin.ModelAdmin):
    list_display = ('newsletter', 'send_date', 'status', 'created_at')
    search_fields = ('newsletter__subject',)
    list_filter = ('status', 'send_date')
    readonly_fields = ('celery_task_id',)
    actions = ['send_now']

    @admin.action(description=_('Send selected tasks now'))
    def send_now(self, request, queryset):
        sent = 0
        for task in queryset:
            do_send_newsletter(task.pk)
            task.refresh_from_db()
            if task.status == 'sent':
                sent += 1
        self.message_user(
            request, _('%(n)d task(s) sent.') % {'n': sent})
