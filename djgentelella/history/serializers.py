from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from djgentelella.serializers import GTDateField, GTDateTimeField


class HistorySerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    action_flag = serializers.SerializerMethodField()
    action_time = GTDateTimeField()
    change_message = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()

    def get_user(self, obj):
        if not obj or not obj.user:
            return _('No user found')
        name = obj.user.get_full_name()
        return name or obj.user.username

    def get_action_flag(self, obj):
        if obj.action_flag == 4:
            return _('Hard deleted')
        elif obj.action_flag == 5:
            return _('Restored')

        return obj.get_action_flag_display()

    def get_change_message(self, obj):
        return obj.change_message

    def get_actions(self, obj):
        # Read-only by default; a subclass with row actions overrides this.
        return {
            'create': False,
            'update': False,
            'destroy': False,
        }

    class Meta:
        model = LogEntry
        fields = '__all__'


class HistoryRelationsMixin(serializers.Serializer):
    """Adds the entry's relations and extra JSON payload to the row.

    Opt-in mixin (``class MySerializer(HistoryRelationsMixin,
    HistorySerializer)``): most listings do not need the payload and the
    extra query per row is not free.
    """

    relations = serializers.SerializerMethodField()
    extra = serializers.SerializerMethodField()

    def get_relations(self, obj):
        rows = []
        for relation in obj.gt_relations.filter(content_type__isnull=False):
            rows.append({
                'content_type': relation.content_type.model,
                'app_label': relation.content_type.app_label,
                'object_id': relation.object_id,
                'data': relation.data,
            })
        return rows

    def get_extra(self, obj):
        row = obj.gt_relations.filter(content_type__isnull=True).first()
        return row.data if row else None


class HistoryDataTableSerializer(serializers.Serializer):
    data = serializers.ListField(child=HistorySerializer(), required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)
