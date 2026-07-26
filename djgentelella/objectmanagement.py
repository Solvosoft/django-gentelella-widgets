from django.core.exceptions import ImproperlyConfigured
from django.http import Http404
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from djgentelella.permission_management import AllPermissionByAction, \
    AnyPermissionByAction


class BaseObjectManagement(viewsets.ModelViewSet):
    serializer_class = {
        'list': None,
        'create': None,
        'update': None,
        'retrieve': None,
        'get_values_for_update': None
    }

    # authentication_classes = (TokenAuthentication, SessionAuthentication)
    # queryset =
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    # search_fields = ['name', 'num_children', ]  # for the global search
    # filterset_class = PersonFilterSet
    # ordering_fields = ['name', 'num_children', 'born_date', 'last_time']
    # ordering = ('-num_children',)  # default order
    operation_type = ''

    def get_serializer_class(self):
        if isinstance(self.serializer_class, dict):
            if self.action in self.serializer_class:
                return self.serializer_class[self.action]
        return super().get_serializer_class()

    def list(self, request, *args, **kwargs):
        base_queryset = self.get_queryset()
        queryset = self.filter_queryset(base_queryset)
        data = self.paginate_queryset(queryset)
        response = {'data': data, 'recordsTotal': base_queryset.count(),
                    'recordsFiltered': queryset.count(),
                    'draw': self.request.GET.get('draw', 1)}
        return Response(self.get_serializer(response).data)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=['get'])
    def get_values_for_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def detail_template(self, request, *args, **kwargs):
        data = {
            "title": "Name <% it.name %>",
            "template": "Description: <% it.description | safe  %>"
        }
        return Response(data)


class BaseInlineObjectManagement(BaseObjectManagement):
    """CRUDAL viewset for objects that belong to a parent instance.

    This is the replacement for the removed ``InlineAjaxCRUD``: instead of
    server rendered AJAX fragments, the related objects are managed with the
    regular ``ObjectCRUD`` javascript (datatable + modals) over a queryset
    restricted to a single parent object.

    Subclasses must define ``parent_model`` and ``parent_field`` (the foreign
    key on the managed model pointing at ``parent_model``)::

        class TaskManagement(BaseInlineObjectManagement):
            queryset = Task.objects.all()
            parent_model = Project
            parent_field = 'project'

    Register it under a URL carrying the parent pk::

        router.register(r'project/(?P<parent_pk>[^/.]+)/task',
                        TaskManagement, 'api-project-task')

    .. warning::

        The parent is what scopes every query and what new objects are attached
        to, so **who may use which parent is an authorization decision**. DRF's
        ``permission_classes`` are per model, not per object: they cannot tell
        one project from another. Override ``get_parent_queryset()`` to narrow
        the parents this request may address::

            def get_parent_queryset(self):
                return Project.objects.filter(owner=self.request.user)

        Without that, any user allowed to call the viewset can name any parent
        pk and read or write that parent's objects.

    The parent pk is read from the URL. Accepting it from the query string or
    the request body instead (``accept_parent_pk_from_request = True``) means a
    client picks its own parent on every call, so only turn it on together with
    a ``get_parent_queryset()`` that filters by requester.
    """

    parent_model = None
    parent_field = None
    parent_url_kwarg = 'parent_pk'
    accept_parent_pk_from_request = False

    def get_parent_pk(self):
        pk = self.kwargs.get(self.parent_url_kwarg)
        if pk is not None or not self.accept_parent_pk_from_request:
            return pk
        pk = self.request.query_params.get(self.parent_url_kwarg)
        if pk is None and isinstance(self.request.data, dict):
            pk = self.request.data.get(self.parent_url_kwarg)
        return pk

    def get_parent_object(self):
        if not hasattr(self, '_parent_object'):
            if self.parent_model is None or self.parent_field is None:
                raise ImproperlyConfigured(
                    '%s must define parent_model and parent_field' %
                    self.__class__.__name__)
            pk = self.get_parent_pk()
            if pk is None:
                raise Http404('No %s given for the inline objects' %
                              self.parent_url_kwarg)
            self._parent_object = get_object_or_404(
                self.get_parent_queryset(), pk=pk)
        return self._parent_object

    def get_parent_queryset(self):
        return self.parent_model._default_manager.all()

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(**{self.parent_field: self.get_parent_object()})

    def perform_create(self, serializer):
        serializer.save(**{self.parent_field: self.get_parent_object()})

    def perform_update(self, serializer):
        serializer.save(**{self.parent_field: self.get_parent_object()})

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['parent_object'] = self.get_parent_object()
        return context


class AuthAllPermBaseObjectManagement(BaseObjectManagement):
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    perms = {
        'list': [],
        'create': [],
        'update': [],
        'retrieve': [],
        'get_values_for_update': []
    }
    permission_classes = (AllPermissionByAction,)


class AuthAnyPermBaseObjectManagement(BaseObjectManagement):
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    perms = {
        'list': [],
        'create': [],
        'update': [],
        'retrieve': [],
        'get_values_for_update': []
    }
    permission_classes = (AnyPermissionByAction,)
