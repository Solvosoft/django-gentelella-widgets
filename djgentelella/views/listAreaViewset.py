import uuid

from django.template.loader import render_to_string
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from djgentelella.serializers.paginators import PageListPagination


class ListAreaViewset(mixins.ListModelMixin, GenericViewSet):
    pagination_class = PageListPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    template_name = 'gentelella/blocks/listcard_template.html'
    filter_form = None
    pagination_top = True
    with_actions = True
    extra_template_context = None
    html_id = None

    def get_html_id(self):
        if self.html_id:
            return self.html_id
        return str(uuid.uuid4())[:4]

    def get_filter_form(self, request):
        return self.filter_form

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response_data = self.get_paginated_response(serializer.data).data
        else:
            serializer = self.get_serializer(queryset, many=True)
            response_data = {'data': serializer.data}

        context = {'with_top_navigation': self.pagination_top,
                   'with_actions': self.with_actions,
                   'id': self.get_html_id(),
                   'form': self.get_filter_form(request)}
        if self.extra_template_context:
            context.update(self.extra_template_context)
        rendered_template = render_to_string(
            self.template_name,
            context=context,
            request=request)

        response_data["template"] = rendered_template  # Agregar plantilla renderizada
        return Response(response_data)
