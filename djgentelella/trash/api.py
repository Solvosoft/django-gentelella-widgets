from djgentelella.objectmanagement import AuthAllPermBaseObjectManagement
from djgentelella.trash.serializer import TrashSerializer, TrashDataTableSerializer
from djgentelella.models import Trash
from djgentelella.trash.filterset import TrashFilter
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import LimitOffsetPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from djgentelella.history.utils import add_log, HARD_DELETION, RESTORE


class TrashViewSet(AuthAllPermBaseObjectManagement):
    serializer_class = {
        "list": TrashDataTableSerializer,
        "destroy": TrashSerializer,
        "create": None,
        "update": None,
        "restore": None,
    }

    perms = {
        "list": ["djgentelella.view_trash"],
        "create": ["djgentelella.add_trash"],
        "update": ["djgentelella.change_trash"],
        "destroy": ["djgentelella.delete_trash"],
        "restore": ["djgentelella.change_trash"],
    }

    queryset = Trash.objects.all()
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ["content_type__model", "object_id", "deleted_by__username"]
    filterset_class = TrashFilter
    ordering_fields = ["created_at"]
    ordering = ("-created_at",)

    def perform_destroy(self, instance):
        add_log(
            self.request.user,
            instance,
            HARD_DELETION,
            instance._meta.verbose_name.title().lower(),
            [],
            change_message=_("Hard deleted"),
        )

        instance.hard_delete()


    @action(detail=True, methods=["POST"])
    def restore(self, request, org_pk=None, pk=None):
        try:
            trash = get_object_or_404(Trash, pk=pk)

            if not trash:
                return Response({"result": False, "detail": _("This registry of trash does not exist.")},
                                status=status.HTTP_400_BAD_REQUEST)

            add_log(
                self.request.user,
                trash.content_object,
                RESTORE,
                "trash",
                [],
                change_message=_("Restored"),
            )

            trash.restore()

            return Response({"result": True, "detail": _("The registry was successfully restored.")}, status=status.HTTP_200_OK)
        except Exception as e:
            print(str(e))
            return Response({"result": False, "detail": _("The registry could not be restored.")}, status=status.HTTP_400_BAD_REQUEST)
