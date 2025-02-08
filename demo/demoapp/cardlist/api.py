from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django.template.loader import render_to_string
from .serializer import PersonSerializer, PersonFilterSet
from ..models import Person


class PersonPagination(PageNumberPagination):
    page_size = 10  # Número de registros por página
    page_size_query_param = 'paginate'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'data': data,
            'recordsTotal': self.page.paginator.count,
            'recordsFiltered': self.page.paginator.count,
            'currentPage': self.page.number,
            'totalPages': self.page.paginator.num_pages,
        })


class PersonViewSet(viewsets.ModelViewSet):
    serializer_class = PersonSerializer
    queryset = Person.objects.all()
    pagination_class = PersonPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ['name', 'num_children']
    filterset_class = PersonFilterSet
    ordering_fields = ['name', 'num_children', 'born_date', 'last_time']
    ordering = ('-num_children',)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response_data = self.get_paginated_response(serializer.data).data
        else:
            serializer = self.get_serializer(queryset, many=True)
            response_data = {'data': serializer.data}

        # Renderiza la plantilla con Squirrelly
        rendered_template = render_to_string('gentelella/cardlist/cardTemplate.html', {})

        response_data["template"] = rendered_template  # Agregar plantilla renderizada
        return Response(response_data)
