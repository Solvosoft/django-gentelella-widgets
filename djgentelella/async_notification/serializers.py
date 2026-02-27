"""
DRF serializers for the async_notification module.

Follows the DataTable wrapper pattern used throughout djgentelella.
"""

from django_filters import FilterSet, DateTimeFromToRangeFilter
from rest_framework import serializers

from djgentelella.serializers import GTDateTimeField
from djgentelella.serializers.selects import GTS2SerializerBase

from djgentelella.async_notification.models import (
    EmailNotification, EmailTemplate,
    NewsLetterTemplate, NewsLetter, NewsLetterTask
)


# =============================================================================
# EmailNotification Serializers
# =============================================================================

class EmailNotificationSerializer(serializers.ModelSerializer):
    """Row serializer for DataTable display."""
    created_at = GTDateTimeField(read_only=True)
    user_display = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()

    class Meta:
        model = EmailNotification
        fields = ('id', 'subject', 'status', 'sent', 'enqueued',
                  'retry_count', 'created_at', 'user_display', 'actions')

    def get_user_display(self, obj):
        return str(obj.user) if obj.user else '-'

    def get_actions(self, obj):
        return {'update': True, 'destroy': True, 'send_email': True}


class EmailNotificationTableSerializer(serializers.Serializer):
    """DataTable wrapper serializer."""
    data = serializers.ListField(
        child=EmailNotificationSerializer(), required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)


class EmailNotificationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating email notifications."""

    class Meta:
        model = EmailNotification
        fields = ('subject', 'message', 'recipients', 'bcc', 'cc',
                  'enqueued', 'send_individually')


class EmailNotificationDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed view of email notifications."""
    created_at = GTDateTimeField(read_only=True)
    updated_at = GTDateTimeField(read_only=True)

    class Meta:
        model = EmailNotification
        fields = ('id', 'subject', 'message', 'recipients', 'bcc', 'cc',
                  'status', 'sent', 'recipients_raw', 'retry_count',
                  'error_message', 'enqueued', 'send_individually',
                  'user', 'created_at', 'updated_at')


class EmailNotificationFilterSet(FilterSet):
    created_at = DateTimeFromToRangeFilter()

    class Meta:
        model = EmailNotification
        fields = {
            'status': ['exact'],
            'sent': ['exact'],
            'enqueued': ['exact'],
        }


# =============================================================================
# EmailTemplate Serializers
# =============================================================================

class EmailTemplateSerializer(serializers.ModelSerializer):
    """Row serializer for DataTable display."""
    created_at = GTDateTimeField(read_only=True)
    actions = serializers.SerializerMethodField()

    class Meta:
        model = EmailTemplate
        fields = ('id', 'code', 'subject', 'created_at', 'actions')

    def get_actions(self, obj):
        return {'update': True, 'destroy': True, 'preview': True}


class EmailTemplateTableSerializer(serializers.Serializer):
    """DataTable wrapper serializer."""
    data = serializers.ListField(
        child=EmailTemplateSerializer(), required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)


class EmailTemplateCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating email templates."""

    class Meta:
        model = EmailTemplate
        fields = ('code', 'subject', 'message', 'bcc', 'cc',
                  'context_code', 'base_template')


class EmailTemplateDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed view."""
    created_at = GTDateTimeField(read_only=True)
    updated_at = GTDateTimeField(read_only=True)

    class Meta:
        model = EmailTemplate
        fields = ('id', 'code', 'subject', 'message', 'bcc', 'cc',
                  'context_code', 'base_template',
                  'created_at', 'updated_at')


# =============================================================================
# NewsLetterTemplate Serializers
# =============================================================================

class NewsLetterTemplateSerializer(serializers.ModelSerializer):
    """Row serializer for DataTable display."""
    created_at = GTDateTimeField(read_only=True)
    actions = serializers.SerializerMethodField()

    class Meta:
        model = NewsLetterTemplate
        fields = ('id', 'title', 'slug', 'model_base', 'created_at', 'actions')

    def get_actions(self, obj):
        return {'update': True, 'destroy': True}


class NewsLetterTemplateTableSerializer(serializers.Serializer):
    """DataTable wrapper serializer."""
    data = serializers.ListField(
        child=NewsLetterTemplateSerializer(), required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)


class NewsLetterTemplateCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating newsletter templates."""

    class Meta:
        model = NewsLetterTemplate
        fields = ('title', 'slug', 'message', 'model_base')


class NewsLetterTemplateDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed view."""
    created_at = GTDateTimeField(read_only=True)
    updated_at = GTDateTimeField(read_only=True)

    class Meta:
        model = NewsLetterTemplate
        fields = ('id', 'title', 'slug', 'message', 'model_base',
                  'created_at', 'updated_at')


class NewsLetterTemplateSelect2Serializer(GTS2SerializerBase):
    """Select2-compatible serializer for newsletter templates."""
    display_fields = 'title'


# =============================================================================
# NewsLetter Serializers
# =============================================================================

class NewsLetterSerializer(serializers.ModelSerializer):
    """Row serializer for DataTable display."""
    created_at = GTDateTimeField(read_only=True)
    template_title = serializers.SerializerMethodField()
    created_by_display = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()

    class Meta:
        model = NewsLetter
        fields = ('id', 'subject', 'template_title',
                  'created_by_display', 'created_at', 'actions')

    def get_template_title(self, obj):
        return obj.template.title if obj.template else '-'

    def get_created_by_display(self, obj):
        return str(obj.created_by) if obj.created_by else '-'

    def get_actions(self, obj):
        return {'update': True, 'destroy': True, 'preview_recipients': True}


class NewsLetterTableSerializer(serializers.Serializer):
    """DataTable wrapper serializer."""
    data = serializers.ListField(
        child=NewsLetterSerializer(), required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)


class NewsLetterCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating newsletters."""

    class Meta:
        model = NewsLetter
        fields = ('template', 'subject', 'message', 'recipients',
                  'bcc', 'cc', 'attached_file', 'filters_querystring')


class NewsLetterDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed view."""
    created_at = GTDateTimeField(read_only=True)
    updated_at = GTDateTimeField(read_only=True)

    class Meta:
        model = NewsLetter
        fields = ('id', 'template', 'subject', 'message', 'recipients',
                  'bcc', 'cc', 'attached_file', 'created_by',
                  'filters_querystring', 'created_at', 'updated_at')


class NewsLetterSelect2Serializer(GTS2SerializerBase):
    """Select2-compatible serializer for newsletters."""
    display_fields = 'subject'


# =============================================================================
# NewsLetterTask Serializers
# =============================================================================

class NewsLetterTaskSerializer(serializers.ModelSerializer):
    """Row serializer for DataTable display."""
    send_date = GTDateTimeField(read_only=True)
    created_at = GTDateTimeField(read_only=True)
    newsletter_subject = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()

    class Meta:
        model = NewsLetterTask
        fields = ('id', 'newsletter_subject', 'send_date', 'status',
                  'created_at', 'actions')

    def get_newsletter_subject(self, obj):
        return obj.newsletter.subject if obj.newsletter else '-'

    def get_actions(self, obj):
        return {'update': True, 'destroy': True}


class NewsLetterTaskTableSerializer(serializers.Serializer):
    """DataTable wrapper serializer."""
    data = serializers.ListField(
        child=NewsLetterTaskSerializer(), required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)


class NewsLetterTaskCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating newsletter tasks."""
    send_date = GTDateTimeField()

    class Meta:
        model = NewsLetterTask
        fields = ('newsletter', 'send_date')


class NewsLetterTaskDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed view."""
    send_date = GTDateTimeField(read_only=True)
    created_at = GTDateTimeField(read_only=True)
    updated_at = GTDateTimeField(read_only=True)

    class Meta:
        model = NewsLetterTask
        fields = ('id', 'newsletter', 'send_date', 'status',
                  'celery_task_id', 'created_at', 'updated_at')


class NewsLetterTaskFilterSet(FilterSet):
    send_date = DateTimeFromToRangeFilter()

    class Meta:
        model = NewsLetterTask
        fields = {
            'status': ['exact'],
            'newsletter': ['exact'],
        }
