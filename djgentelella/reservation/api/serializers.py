from django_filters import FilterSet
from rest_framework import serializers
from ..models import Product


class ProductSerializer(serializers.ModelSerializer):
    actions = serializers.SerializerMethodField()

    def get_actions(self, obj):
        return {}

    class Meta:
        model = Product
        fields = ['description', 'id', 'actions']


class ProductDataTableSerializer(serializers.Serializer):
    data = serializers.ListField(child=ProductSerializer(), required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)


class ProductFilter(FilterSet):

    class Meta:
        model = Product
        fields = {'id': ['exact']}
