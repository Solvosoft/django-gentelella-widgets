from django.contrib import admin

from djgentelella.async_notification.models import (
    EmailTemplate, EmailNotification, AttachedFile,
    NewsLetterTemplate, NewsLetter, NewsLetterTask
)


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('code', 'subject', 'created_at', 'updated_at')
    search_fields = ('code', 'subject')
    list_filter = ('created_at',)


@admin.register(EmailNotification)
class EmailNotificationAdmin(admin.ModelAdmin):
    list_display = ('subject', 'status', 'sent', 'enqueued',
                    'retry_count', 'created_at')
    search_fields = ('subject', 'recipients')
    list_filter = ('status', 'sent', 'enqueued', 'created_at')
    readonly_fields = ('recipients_raw', 'error_message', 'retry_count')


@admin.register(AttachedFile)
class AttachedFileAdmin(admin.ModelAdmin):
    list_display = ('file', 'content_type', 'object_id',
                    'is_inline', 'created_at')
    list_filter = ('is_inline', 'content_type')


@admin.register(NewsLetterTemplate)
class NewsLetterTemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'model_base', 'created_at')
    search_fields = ('title', 'slug')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(NewsLetter)
class NewsLetterAdmin(admin.ModelAdmin):
    list_display = ('subject', 'template', 'created_by', 'created_at')
    search_fields = ('subject',)
    list_filter = ('created_at',)


@admin.register(NewsLetterTask)
class NewsLetterTaskAdmin(admin.ModelAdmin):
    list_display = ('newsletter', 'send_date', 'status', 'created_at')
    search_fields = ('newsletter__subject',)
    list_filter = ('status', 'send_date')
    readonly_fields = ('celery_task_id',)
