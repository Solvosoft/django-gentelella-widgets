from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from djgentelella.models import Trash
from djgentelella.serializers import GTDateTimeField


class TrashSerializer(serializers.ModelSerializer):
    actions = serializers.SerializerMethodField()
    object_id = serializers.IntegerField(read_only=True)
    model_name = serializers.SerializerMethodField()
    created_at = GTDateTimeField()
    deleted_by = serializers.SerializerMethodField()

    def get_actions(self, obj):
        user = self.context["request"].user
        return {
            "restore": user.has_perm("djgentelella.delete_trash"),
            "destroy": user.has_perm("djgentelella.delete_trash"),
        }

    def get_model_name(self, obj):
        if obj.content_object is None:
            return _("Deleted object")

        if obj.content_type.model:
            return obj.content_type.model

        return "-"

    def get_deleted_by(self, obj):
        if obj.deleted_by:
            return str(obj.deleted_by)
        return "-"

    class Meta:
        model = Trash
        fields = "__all__"


class TrashDataTableSerializer(serializers.Serializer):
    data = serializers.ListField(child=TrashSerializer(), required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)

