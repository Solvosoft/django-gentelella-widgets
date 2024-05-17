from django_filters import FilterSet
from rest_framework import serializers
from djgentelella.reservation.models import Product, Reservation, DescriptionTransaction


class ActionsBase(serializers.Serializer):
    actions = serializers.SerializerMethodField()

    def get_actions(self, obj):
        return {
            "destroy": True,
            "list": True,
            "create": True,
            "update": True
        }


class ProductSerializer(serializers.ModelSerializer, ActionsBase):

    class Meta:
        model = Product
        fields = ['id', 'actions']


class ProductDataTableSerializer(serializers.Serializer):
    data = serializers.ListField(child=ProductSerializer(), required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)


class ProductFilter(FilterSet):

    class Meta:
        model = Product
        fields = {'id': ['exact']}


class ReservationSerializer(serializers.ModelSerializer, ActionsBase):

    class Meta:
        model = Reservation
        fields = ['id', 'actions']


class ReservationDataTableSerializer(serializers.Serializer):
    data = serializers.ListField(child=ReservationSerializer(), required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)


class ReservationFilter(FilterSet):

    class Meta:
        model = Reservation
        fields = {'id': ['exact']}


class DescriptionTransactionSerializer(serializers.ModelSerializer, ActionsBase):

    class Meta:
        model = DescriptionTransaction
        fields = ['id', 'actions']


class DescriptionTransactionDataTableSerializer(serializers.Serializer):
    data = serializers.ListField(child=ReservationSerializer(), required=True)
    draw = serializers.IntegerField(required=True)
    recordsFiltered = serializers.IntegerField(required=True)
    recordsTotal = serializers.IntegerField(required=True)


class DescriptionTransactionFilter(FilterSet):

    class Meta:
        model = DescriptionTransaction
        fields = {'id': ['exact']}
