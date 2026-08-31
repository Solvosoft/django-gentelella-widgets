import logging

from djgentelella.objectmanagement import AuthAllPermBaseObjectManagement
from djgentelella.trash.serializer import TrashSerializer, TrashDataTableSerializer
from djgentelella.models import Trash
from djgentelella.utils import contenttypes_from_labels
from djgentelella.trash.filterset import TrashFilter
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import LimitOffsetPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.utils.translation import gettext_lazy as _
from djgentelella.history.utils import add_log, HARD_DELETION, RESTORE

logger = logging.getLogger(__name__)


class TrashViewSet(AuthAllPermBaseObjectManagement):
    serializer_class = {
        'list': TrashDataTableSerializer,
        'destroy': TrashSerializer,
        'create': None,
        'update': None,
        'restore': None,
    }

    perms = {
        'list': ['djgentelella.view_trash'],
        'create': ['djgentelella.add_trash'],
        'update': ['djgentelella.change_trash'],
        'destroy': ['djgentelella.delete_trash'],
        'restore': ['djgentelella.change_trash'],
    }

    queryset = Trash.objects.all()
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ['content_type__model', 'object_id', 'deleted_by__username']
    filterset_class = TrashFilter
    ordering_fields = ['created_at']
    ordering = ('-created_at',)

    def get_queryset(self):
        # list() computes recordsTotal from get_queryset(), so both the
        # related filter and the tenant scope narrow the count too.
        queryset = super().get_queryset()
        queryset = self.filter_by_related(queryset)
        return self.scope_queryset(queryset)

    def filter_by_related(self, queryset):
        """Entries whose TrashRelation points at the given object.

        Driven by the generic query params ``related_contenttype``
        (``app.model``) and ``related_id`` (repeatable), mirroring
        ``HistoryViewSet``.
        """
        related_ct = self.request.GET.get('related_contenttype')
        if not related_ct:
            return queryset
        ctypes = contenttypes_from_labels([related_ct])
        if not ctypes.exists():
            return queryset.none()
        filters = {'gt_relations__content_type__in': ctypes}
        related_ids = self.request.GET.getlist('related_id')
        if related_ids:
            filters['gt_relations__object_id__in'] = related_ids
        return queryset.filter(**filters).distinct()

    def scope_queryset(self, queryset):
        """Last word on what this request may see.

        It guards the detail actions too -- restore and destroy resolve
        through ``get_object()``.  The default is everything; a multi-tenant
        project overrides this to
        cut the trash down to the requester's organization, typically through
        the ``gt_relations`` join.
        """
        return queryset

    def get_log_related_objects(self, trash):
        """Hook for subclasses: instances to link the log entry to."""
        return None

    def perform_destroy(self, instance):
        # Log against the destroyed object's real model, not against Trash:
        # "an object of model Trash was hard deleted" says nothing.
        target = instance.content_object or instance
        add_log(
            self.request.user,
            target,
            HARD_DELETION,
            target._meta.verbose_name.title().lower(),
            [],
            change_message=_('Hard deleted'),
            related_objects=self.get_log_related_objects(instance),
        )

        instance.hard_delete()

    @action(detail=True, methods=['POST'])
    def restore(self, request, org_pk=None, pk=None):
        # Before the try: a missing entry is a 404, not a failed restore. The
        # catch-all below would otherwise swallow the Http404 and answer 400
        # with "could not be restored", which is the wrong status and the
        # wrong reason for the commonest case -- someone else already restored
        # it from another tab. DRF's exception handler turns it into
        # {"detail": ...} JSON, the same shape the caller already reads.
        # It goes through get_object() so that a subclass scoping
        # get_queryset() (a per-tenant trash) also scopes what can be restored.
        trash = self.get_object()

        if trash.content_object is None:
            return Response(
                {
                    'result': False,
                    'detail': _(
                        'The original object no longer exists; the entry '
                        'can only be permanently removed.'
                    ),
                },
                status=status.HTTP_410_GONE,
            )

        try:
            add_log(
                self.request.user,
                trash.content_object,
                RESTORE,
                None,
                [],
                change_message=_('Restored'),
                related_objects=self.get_log_related_objects(trash),
            )

            trash.restore()

            return Response(
                {
                    'result': True,
                    'detail': _('The registry was successfully restored.'),
                },
                status=status.HTTP_200_OK,
            )
        except Exception:
            # Broad on purpose -- restore() reaches arbitrary model code
            # through the generic relation -- but the reason has to reach the
            # log, since the client only ever sees the generic message below.
            logger.exception('Trash %s could not be restored', pk)
            return Response(
                {'result': False, 'detail': _('The registry could not be restored.')},
                status=status.HTTP_400_BAD_REQUEST,
            )
