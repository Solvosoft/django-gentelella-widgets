from demoapp.models import Customer
from djgentelella.objectmanagement import AuthAllPermBaseObjectManagement
from demoapp.trash.serializer import CustomerSerializer, CustomerDataTableSerializer, \
    CustomerValidateSerializer
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from djgentelella.history.api import BaseViewSetWithLogs
from djgentelella.history.utils import add_log, DELETION
from django.utils.translation import gettext_lazy as _


class CustomerViewSet(BaseViewSetWithLogs):
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
        # add log for history
        add_log(
            self.request.user,
            instance,
            DELETION,
            "customer",
            [],
            change_message=_("Deleted"),
        )
        # add user to deleted_by for trash
        instance.delete(user=self.request.user)

