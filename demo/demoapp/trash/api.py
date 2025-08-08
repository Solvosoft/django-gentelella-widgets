from demoapp.models import Customer
from djgentelella.objectmanagement import AuthAllPermBaseObjectManagement
from demoapp.trash.serializer import CustomerSerializer, CustomerDataTableSerializer, \
    CustomerValidateSerializer
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend


class CustomerViewSet(AuthAllPermBaseObjectManagement):
    serializer_class = {
        "list": CustomerDataTableSerializer,
        "destroy": CustomerSerializer,
        "create": CustomerValidateSerializer,
        "update": CustomerValidateSerializer,
    }

    perms = {
        "list": [],
        "create": [],
        "update": [],
        "destroy": [],
    }

    permission_classes = ()

    queryset = Customer.objects.all()
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ["name"]
    filterset_class = None
    ordering_fields = ["name"]
    ordering = ("id",)

    # important to define for delete
    def perform_destroy(self, instance):
        # add user to deleted_by
        instance.delete(user=self.request.user)

