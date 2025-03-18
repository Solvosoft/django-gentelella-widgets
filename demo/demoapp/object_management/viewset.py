from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import LimitOffsetPagination

from djgentelella.objectmanagement import BaseObjectManagement
from . import serializer
from ..models import ObjectManagerDemoModel


class ObjectManagerDemoModelManagement(BaseObjectManagement):
    serializer_class = {
        'list': serializer.ObjectManagerDemoModelTableSerializer,
        'create': serializer.ObjectManagerDemoModelCreateSerializer,
        'update': serializer.ObjectManagerDemoModelCreateSerializer,
        'retrieve': serializer.ObjectManagerDemoModelUpdateSerializer,
        'get_values_for_update': serializer.ObjectManagerDemoModelUpdateSerializer
    }
    # permission_classes = (IsAuthenticated,)
    # authentication_classes = (TokenAuthentication, SessionAuthentication)
    queryset = ObjectManagerDemoModel.objects.all()
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ['name', 'description', ]  # for the global search
    filterset_class = serializer.ObjectManagerDemoModelFilterSet
    ordering_fields = ['name', 'float_number', 'born_date', 'last_time']
    ordering = ('-pk',)  # default order
    operation_type = ''
