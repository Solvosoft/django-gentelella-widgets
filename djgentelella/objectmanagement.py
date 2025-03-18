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
        queryset = self.filter_queryset(self.get_queryset())
        data = self.paginate_queryset(queryset)
        response = {'data': data, 'recordsTotal': self.queryset.count(),
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
