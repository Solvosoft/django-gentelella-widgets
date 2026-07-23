"""
DRF serializers for the async_notification module.

Follows the DataTable wrapper pattern used throughout djgentelella.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters import FilterSet, DateTimeFromToRangeFilter
from rest_framework import serializers

from djgentelella.fields.files import GTBase64FileField
from djgentelella.serializers import GTDateTimeField
from djgentelella.serializers.selects import (
    GTS2SerializerBase, ChoicesGTS2Serializer,
)

from djgentelella.async_notification.models import (
    EmailNotification, EmailTemplate,
    NewsLetterTemplate, NewsLetter, NewsLetterTask,
    validate_recipient_list,
)
from djgentelella.async_notification.sending import link_body_attachments
from djgentelella.async_notification.settings import (
    ASYNC_NOTIFICATION_BASE_TEMPLATES, ASYNC_NEWS_BASE_MODELS,
)


def _base_template_field():
    """Select2-shaped ({id, text}) field for the base_template CharField.

    ``base_template`` is a plain string choice, not a model relation, but
    the compose-modal JS (``fill_form``) restores select2 widgets from an
    ``{id, text}`` pair regardless of what backs the choice.
    """
    return ChoicesGTS2Serializer(
        choices={key: key for key in ASYNC_NOTIFICATION_BASE_TEMPLATES})


def _model_base_field():
    """Select2-shaped field for NewsLetterTemplate.model_base."""
    return ChoicesGTS2Serializer(
        choices={key: value[1] for key, value in ASYNC_NEWS_BASE_MODELS.items()})


class InlineAttachmentSerializerMixin:
    """Links inline images referenced in ``message`` to the saved object."""

    def create(self, validated_data):
        instance = super().create(validated_data)
        link_body_attachments(instance)
        return instance

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        link_body_attachments(instance)
        return instance


class RecipientListField(serializers.JSONField):
    """Recipients field that accepts a single email, a CSV string, or a list.

    A single address is simply a one-element list, so the UI never forces
    the user to type list syntax. Coercion happens in ``to_internal_value``
    (before validators run), then the shared recipient validator applies.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('required', False)
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data):
        if data in (None, ''):
            data = []
        elif isinstance(data, str):
            data = [t.strip() for t in data.split(',') if t.strip()]
        elif isinstance(data, (list, tuple)):
            data = [str(t).strip() for t in data if str(t).strip()]
        else:
            self.fail('invalid')
        try:
            validate_recipient_list(data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return data


class RecipientFieldsMixin(serializers.Serializer):
    """Declares recipient/bcc/cc as coercing RecipientListFields."""
    recipients = RecipientListField()
    bcc = RecipientListField()
    cc = RecipientListField()


# =============================================================================
# EmailNotification Serializers
# =============================================================================

class EmailNotificationSerializer(serializers.ModelSerializer):
    """Row serializer for DataTable display."""
    created_at = GTDateTimeField(read_only=True)
    sent = serializers.BooleanField(read_only=True)
    user_display = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()

    class Meta:
        model = EmailNotification
        fields = ('id', 'subject', 'status', 'sent', 'enqueued',
                  'retry_count', 'created_at', 'user_display', 'actions')

    def get_user_display(self, obj):
        return str(obj.user) if obj.user else '-'

    def get_actions(self, obj):
        return {'update': True, 'destroy': True, 'send_email': True,
                'preview': True}


class EmailNotificationTableSerializer(serializers.Serializer):
    """DataTable wrapper serializer."""
    data = serializers.ListField(
        child=EmailNotificationSerializer(), required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)


class EmailNotificationCreateSerializer(InlineAttachmentSerializerMixin,
                                        RecipientFieldsMixin,
                                        serializers.ModelSerializer):
    """Serializer for creating/updating email notifications."""

    class Meta:
        model = EmailNotification
        fields = ('subject', 'message', 'recipients', 'bcc', 'cc',
                  'base_template', 'enqueued', 'send_individually',
                  'is_promotional')


class EmailNotificationDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed view of email notifications."""
    created_at = GTDateTimeField(read_only=True)
    updated_at = GTDateTimeField(read_only=True)
    sent = serializers.BooleanField(read_only=True)
    base_template = _base_template_field()

    class Meta:
        model = EmailNotification
        fields = ('id', 'subject', 'message', 'recipients', 'bcc', 'cc',
                  'status', 'sent', 'base_template', 'recipients_raw',
                  'retry_count', 'max_retries', 'error_message', 'enqueued',
                  'send_individually', 'is_promotional', 'user',
                  'created_at', 'updated_at')


class EmailNotificationFilterSet(FilterSet):
    created_at = DateTimeFromToRangeFilter()

    class Meta:
        model = EmailNotification
        fields = {
            'status': ['exact'],
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
    base_template = _base_template_field()

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
        return {'update': True, 'destroy': True, 'preview': True}


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
        fields = ('title', 'slug', 'message', 'model_base', 'base_template')


class NewsLetterTemplateDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed view."""
    created_at = GTDateTimeField(read_only=True)
    updated_at = GTDateTimeField(read_only=True)
    base_template = _base_template_field()
    model_base = _model_base_field()

    class Meta:
        model = NewsLetterTemplate
        fields = ('id', 'title', 'slug', 'message', 'model_base',
                  'base_template', 'created_at', 'updated_at')


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


class NewsLetterCreateSerializer(InlineAttachmentSerializerMixin,
                                 RecipientFieldsMixin,
                                 serializers.ModelSerializer):
    """Serializer for creating/updating newsletters."""

    # The compose modal submits the form as JSON (base64-encoded files),
    # not multipart, so a plain FileField (which expects request.FILES)
    # rejects it with "not a file. Check the encoding type on the form."
    attached_file = GTBase64FileField(required=False, allow_empty_file=True)


    class Meta:
        model = NewsLetter
        fields = ('template', 'subject', 'message', 'recipients',
                  'bcc', 'cc', 'base_template', 'attached_file',
                  'filters_querystring')


class NewsLetterDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed view."""
    created_at = GTDateTimeField(read_only=True)
    updated_at = GTDateTimeField(read_only=True)
    # Same field as the create serializer, so the edit form gets back
    # {name, url} (what the file-link renderer in fill_form expects)
    # instead of a bare URL string.
    attached_file = GTBase64FileField(required=False, allow_empty_file=True)
    base_template = _base_template_field()
    template = NewsLetterTemplateSelect2Serializer(many=False)

    class Meta:
        model = NewsLetter
        fields = ('id', 'template', 'subject', 'message', 'recipients',
                  'bcc', 'cc', 'base_template', 'attached_file', 'created_by',
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
        return {'update': True, 'destroy': True, 'send_now': True}


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
