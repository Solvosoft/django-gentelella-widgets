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
            return _("No user found")
        name = obj.user.get_full_name()
        return name or obj.user.username

    def get_action_flag(self, obj):
        if obj.action_flag == 4:
            return _("Hard deleted")
        elif obj.action_flag == 5:
            return _("Restored")

        return obj.get_action_flag_display()

    def get_change_message(self, obj):
        return obj.change_message

    def get_actions(self, obj):
        return {
            "create": False,
            "update": False,
            "destroy": False,
        }

    class Meta:
        model = LogEntry
        fields = "__all__"


class HistoryDataTableSerializer(serializers.Serializer):
    data = serializers.ListField(child=HistorySerializer(), required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)

