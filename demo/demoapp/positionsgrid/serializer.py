from rest_framework import serializers

from ..models import WarehouseBox


class WarehouseBoxSerializer(serializers.ModelSerializer):
    class Meta:
        model = WarehouseBox
        fields = ['id', 'code', 'content', 'quantity', 'row', 'col']


class RowSerializer(serializers.Serializer):
    row = serializers.IntegerField(min_value=0)


class ColSerializer(serializers.Serializer):
    col = serializers.IntegerField(min_value=0)


class CreateBoxSerializer(serializers.Serializer):
    row = serializers.IntegerField(min_value=0)
    col = serializers.IntegerField(min_value=0)
    code = serializers.CharField(max_length=50, required=False, allow_blank=True)
    content = serializers.CharField(max_length=150, required=False, allow_blank=True)
    quantity = serializers.IntegerField(min_value=0, required=False)


class MoveBoxSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    row = serializers.IntegerField(min_value=0)
    col = serializers.IntegerField(min_value=0)


class BoxSerializer(serializers.Serializer):
    id = serializers.IntegerField()
