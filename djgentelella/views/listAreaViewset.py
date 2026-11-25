import uuid

from django.template.loader import render_to_string
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from djgentelella.serializers.paginators import PageListPagination


class ListAreaViewset(mixins.ListModelMixin, GenericViewSet):
    DISTRIBUTE = {
        '1': ('', 'p-3'),
        '1/1': ('col-md-6', 'col-md-6 p-3 p-md-0'),
        '2/1': ('col-md-8', 'col-md-4 p-3 p-md-0'),
        '3/1': ('col-md-9', 'col-md-3 p-3 p-md-0'),
        '1/1p': ('col-md-6', 'col-md-6 p-0 p-md-3'),
        '2/1p': ('col-md-8', 'col-md-4 p-0 p-md-3'),
        '3/1p': ('col-md-9', 'col-md-3 p-0 p-md-3'),
    }

    pagination_class = PageListPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    template_name = 'gentelella/blocks/listcard_template.html'
    filter_form = None
    pagination_top = True
    distribution_value = '1/1'
    with_actions = True
    extra_template_context = None
    html_id = None

    def distribution(self):
        return self.DISTRIBUTE.get(self.distribution_value, ('col-md-6', 'col-md-6'))

    def get_html_id(self):
        if self.html_id:
            return self.html_id
        return str(uuid.uuid4())[:4]

    def get_filter_form(self, request):
        if self.filter_form is None:
            return None
        return self.filter_form(data=request.GET)

    def get_page_size_options(self, request):
        pagesize = self.paginator.get_page_size(request)
        sizes = [5, 10, 15, 25, 50, 100, 500]
        page_size_opt = []
        found = False
        for size in sizes:
            page_size_opt.append(
                {'id': size, 'selected': size == pagesize}
            )
            if size == pagesize:
                found = True
        if not found:
            page_size_opt.append({'id': pagesize, 'selected': True})
        return page_size_opt

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response_data = self.get_paginated_response(serializer.data).data
        else:
            serializer = self.get_serializer(queryset, many=True)
            response_data = {'data': serializer.data}

        response_data.update(self.template_response(request))
        return Response(response_data)

    def get_template_context(self, request):
        """The context ``template_name`` is rendered with."""
        context = {'with_top_navigation': self.pagination_top,
                   'with_actions': self.with_actions,
                   'id': self.get_html_id(),
                   'page_size_options': self.get_page_size_options(request),
                   'form': self.get_filter_form(request),
                   'distribution': self.distribution()}
        if self.extra_template_context:
            context.update(self.extra_template_context)
        return context

    def template_response(self, request):
        """What the response carries next to the rows: ``template`` (the
        Squirrelly template ``CardList`` renders them with) and ``actions``.

        A subclass that reads its rows otherwise -- the ``cards`` design
        component -- builds its own ``list()`` and adds these.
        """
        return {'template': render_to_string(
                    self.template_name, context=self.get_template_context(request),
                    request=request),
                'actions': self.get_actions()}

    def get_actions(self):
        return []
