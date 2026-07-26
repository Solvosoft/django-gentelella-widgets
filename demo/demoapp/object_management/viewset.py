from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from djgentelella.objectmanagement import BaseObjectManagement, \
    BaseInlineObjectManagement
from . import serializer
from ..models import ObjectManagerDemoModel, ObjectManagerDemoNote


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


class ObjectManagerDemoNoteManagement(BaseInlineObjectManagement):
    """Notes of one ObjectManagerDemoModel, the replacement for InlineAjaxCRUD.

    This is the example the documentation points at, so it is wired the way a
    real one should be: authenticated, and with ``get_parent_queryset()``
    overridden -- the parent is what scopes every query, and DRF permissions
    cannot tell one parent object from another.
    """
    serializer_class = {
        'list': serializer.ObjectManagerDemoNoteTableSerializer,
        'create': serializer.ObjectManagerDemoNoteSerializer,
        'update': serializer.ObjectManagerDemoNoteSerializer,
        'retrieve': serializer.ObjectManagerDemoNoteSerializer,
        'get_values_for_update': serializer.ObjectManagerDemoNoteSerializer
    }
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    queryset = ObjectManagerDemoNote.objects.all()
    parent_model = ObjectManagerDemoModel
    parent_field = 'demo_object'

    search_fields = ['title', 'body']
    filterset_class = serializer.ObjectManagerDemoNoteFilterSet
    ordering_fields = ['title', 'created']
    ordering = ('-pk',)

    def get_parent_queryset(self):
        # The demo model has no owner, so every authenticated user may address
        # every parent. In a real app this is where you filter:
        #     return Project.objects.filter(owner=self.request.user)
        return super().get_parent_queryset()

    @action(detail=False, methods=['get'])
    def detail_template(self, request, *args, **kwargs):
        return Response({
            "title": "<% it.title %>",
            # `safe` because the notes are written in a rich text editor. It
            # means whoever may write a note may inject html into this panel:
            # drop `| safe` if that is not who you want writing them.
            "template": "<% it.body | safe %>"
        })
