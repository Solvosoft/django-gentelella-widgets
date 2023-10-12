from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import LimitOffsetPagination

from djgentelella.objectmanagement import BaseObjectManagement
from ..datatables import serializer
from ..datatables.serializer import PersonFilterSet
from ..models import Person


class PersonObjectMangement(BaseObjectManagement):
    serializer_class = {
        'list': serializer.PersonDataTableSerializer,
        'create': serializer.PersonCreateSerializer,
        'update': serializer.PersonCreateSerializer,
        'retrieve': serializer.PersonUpdateSerializer,
        'get_values_for_update': serializer.PersonUpdateSerializer
    }
    # permission_classes = (IsAuthenticated,)
    # authentication_classes = (TokenAuthentication, SessionAuthentication)
    queryset = Person.objects.all()
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ['name', 'num_children', ]  # for the global search
    filterset_class = PersonFilterSet
    ordering_fields = ['name', 'num_children', 'born_date', 'last_time']
    ordering = ('-num_children',)  # default order
    operation_type = ''
