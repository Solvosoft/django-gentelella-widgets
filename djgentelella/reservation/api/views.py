from django.contrib.contenttypes.models import ContentType
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import LimitOffsetPagination

from djgentelella.objectmanagement import AuthAllPermBaseObjectManagement
from djgentelella.reservation.api import serializers
from djgentelella.reservation.models import Product, Reservation, DescriptionTransaction


class ReservationManagementViewset(AuthAllPermBaseObjectManagement):
    serializer_class = {
        'list': serializers.ReservationDataTableSerializer,
        'create': serializers.ReservationSerializer,
        'destroy': serializers.ReservationSerializer,
        'update': serializers.ReservationSerializer
    }
    perms = {
        'list': ["reservation.view_reservation"],
        'update': ["reservation.change_reservation", "reservation.view_reservation"],
        'create': ["reservation.add_reservation", "reservation.view_reservation"],
        'destroy': ["reservation.delete_reservation", "reservation.view_reservation"]
    }

    queryset = Reservation.objects.all()
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ['id']
    filterset_class = serializers.ReservationFilter
    ordering_fields = []
    ordering = ('id',)
    app_label, model, object_id = None, None, None

    def filter_queryset(self, queryset):
        queryset = super().get_queryset()

        if self.app_label and self.model and self.object_id:
            content_type = ContentType.objects.get(app_label=self.app_label,
                                                   model=self.model)
            queryset = queryset.filter(content_type=content_type,
                                       object_id=self.object_id)
        return queryset

    def list(self, request, *args, **kwargs):
        if all(key in kwargs for key in ["app_label", "model", "object_id"]):
            self.app_label = kwargs['app_label']
            self.model = kwargs['model']
            self.object_id = kwargs['object_id']
        return super().list(request, *args, **kwargs)


class ProductManagementViewset(AuthAllPermBaseObjectManagement):
    serializer_class = {
        'list': serializers.ProductDataTableSerializer,
        'destroy': serializers.ProductSerializer,
        'create': serializers.ProductSerializer,
        'update': serializers.ProductSerializer
    }
    perms = {
        'list': ["reservation.view_product"],
        'update': ["reservation.change_product", "reservation.view_product"],
        'create': ["reservation.add_product", "reservation.view_product"],
        'destroy': ["reservation.delete_product", "reservation.view_product"]
    }

    queryset = Product.objects.all()
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ['id']
    filterset_class = serializers.ProductFilter
    ordering_fields = []
    ordering = ('id',)
    app_label, model, object_id = None, None, None

    def filter_queryset(self, queryset):
        queryset = super().get_queryset()

        if self.app_label and self.model and self.object_id:
            content_type = ContentType.objects.get(app_label=self.app_label,
                                                   model=self.model)
            queryset = queryset.filter(reservation__content_type=content_type,
                                       reservation_object_id=self.object_id)
        return queryset

    def list(self, request, *args, **kwargs):
        if all(key in kwargs for key in ["app_label", "model", "object_id"]):
            self.app_label = kwargs['app_label']
            self.model = kwargs['model']
            self.object_id = kwargs['object_id']
        return super().list(request, *args, **kwargs)


class DescriptionTransactionManagementViewset(AuthAllPermBaseObjectManagement):
    serializer_class = {
        'list': serializers.DescriptionTransactionDataTableSerializer,
        'create': serializers.DescriptionTransactionSerializer,
        'destroy': serializers.DescriptionTransactionSerializer,
        'update': serializers.DescriptionTransactionSerializer
    }
    perms = {
        'list': ["reservation.view_descriptiontransaction"],
        'update': ["reservation.change_descriptiontransaction", "reservation.view_descriptiontransaction"],
        'create': ["reservation.add_descriptiontransaction", "reservation.view_descriptiontransaction"],
        'destroy': ["reservation.delete_descriptiontransaction", "reservation.view_descriptiontransaction"]
    }

    queryset = DescriptionTransaction.objects.all()
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ['id']
    filterset_class = serializers.ProductFilter
    ordering_fields = []
    ordering = ('id',)
    app_label, model, object_id = None, None, None

    def filter_queryset(self, queryset):
        queryset = super().get_queryset()

        if self.app_label and self.model and self.object_id:
            content_type = ContentType.objects.get(app_label=self.app_label,
                                                   model=self.model)
            queryset = queryset.filter(reservation__content_type=content_type,
                                       reservation_object_id=self.object_id)
        return queryset

    def list(self, request, *args, **kwargs):
        if all(key in kwargs for key in ["app_label", "model", "object_id"]):
            self.app_label = kwargs['app_label']
            self.model = kwargs['model']
            self.object_id = kwargs['object_id']
        return super().list(request, *args, **kwargs)
