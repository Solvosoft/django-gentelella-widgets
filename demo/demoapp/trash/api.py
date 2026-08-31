from demoapp.models import Customer
from djgentelella.objectmanagement import AuthAllPermBaseObjectManagement
from demoapp.trash.serializer import CustomerSerializer, CustomerDataTableSerializer, \
    CustomerValidateSerializer
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from djgentelella.history.api import BaseViewSetWithLogs


class CustomerViewSet(BaseViewSetWithLogs):
    serializer_class = {
        'list': CustomerDataTableSerializer,
        'destroy': CustomerSerializer,
        'create': CustomerValidateSerializer,
        'update': CustomerValidateSerializer,
    }

    perms = {
        'list': [],
        'create': [],
        'update': [],
        'destroy': [],
    }

    permission_classes = ()

    queryset = Customer.objects.all()
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ['name']
    filterset_class = None
    ordering_fields = ['name']
    ordering = ('id',)

    # perform_destroy needs no override: BaseViewSetWithLogs logs the
    # deletion, soft deletes through the trash and records deleted_by. This
    # hook only adds an extra JSON payload to every entry (merged with the
    # request metadata the base captures: browser, ip, method, path) -- filter
    # it with ?extra={"source": "demo"} on api-history-list.
    def get_log_extra(self, instance):
        return {'source': 'demo'}
