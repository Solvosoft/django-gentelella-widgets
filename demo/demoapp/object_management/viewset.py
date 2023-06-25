from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from ..datatables import serializer
from ..datatables.serializer import PersonFilterSet
from ..models import Person


class PersonObjectMangement(viewsets.ModelViewSet):
    serializer_class = {
        'list': serializer.PersonDataTableSerializer,
        'create': serializer.PersonCreateSerializer,
        'update': serializer.PersonCreateSerializer,
        'retrieve': serializer.PersonUpdateSerializer,
        'update_values': serializer.PersonUpdateSerializer
    }
    #    permission_classes = (IsAuthenticated,)
    #    authentication_classes = (TokenAuthentication, SessionAuthentication)
    queryset = Person.objects.all()
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ['name', 'num_children', ]  # for the global search
    filterset_class = PersonFilterSet
    ordering_fields = ['name', 'num_children', 'born_date', 'last_time']
    ordering = ('-num_children',)  # default order
    operation_type = ''

    def get_serializer_class(self):
        if isinstance(self.serializer_class, dict):
            if self.action in self.serializer_class:
                return self.serializer_class[self.action]
        return super().get_serializer_class()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        data = self.paginate_queryset(queryset)
        response = {'data': data, 'recordsTotal': Person.objects.count(),
                    'recordsFiltered': queryset.count(),
                    'draw': self.request.GET.get('draw', 1)}
        return Response(self.get_serializer(response).data)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=['get'])
    def update_values(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def detail_template(self, request, *args, **kwargs):
        data = {
            "template": "Name: {{it.name}}"
        }
        return Response(data)
