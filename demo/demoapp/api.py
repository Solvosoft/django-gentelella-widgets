from rest_framework import viewsets, renderers
from rest_framework.pagination import LimitOffsetPagination

from demoapp.models import Person
from demoapp.serializers import PersonTableSerializer
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter


class PersonViewSet(viewsets.ModelViewSet):
    queryset = Person.objects.all()
    serializer_class = PersonTableSerializer
    model = Person
    pagination_class = LimitOffsetPagination
    ordering = ('-pk',)  # default order
    filter_backends = (SearchFilter, OrderingFilter)
    rel_instance_name = 'relperson__number'

    def extract_relinst(self):
        relinst = self.request.GET.get('relinst', '-1')
        if relinst == -1 or relinst == '-1':
            return None
        return relinst

    def get_queryset(self):
        queryset = super().get_queryset()
        relinst = self.extract_relinst()
        if relinst is not None:
            queryset = queryset.filter(**{self.rel_instance_name: relinst})
        else:
            queryset = queryset.none()
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        data = self.paginate_queryset(queryset)
        response = {'data': data, 'recordsTotal': self.model.objects.count(), 'recordsFiltered': queryset.count(),
                    'draw': self.request.GET.get('draw', 1)}
        return Response(self.get_serializer(response).data)
