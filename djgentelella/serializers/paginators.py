from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class PageListPagination(PageNumberPagination):
    page_size_query_param = 'page_size'

    def get_paginated_response(self, data):
        return Response({
            'data': data,
            'recordsTotal': self.page.paginator.count,
            'recordsFiltered': len(data),
            'currentPage': self.page.number,
            'totalPages': self.page.paginator.num_pages,
        })
