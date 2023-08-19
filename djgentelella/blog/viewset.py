from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import LimitOffsetPagination

from djgentelella.blog.blog import BaseObjectBlog

#from djgentelella.datatables import  serializer
#from demoapp.datatables.serializer import PersonFilterSet



from djgentelella.datatables import  serializer
from djgentelella.datatables.serializer import BlogFilterSet


#from demoapp.models import Person

from djgentelella.blog.models import Entry


class PersonBLog(BaseObjectBlog):
    serializer_class = {
        'list': serializer.BlogDataTableSerializer,
        'create': serializer.BlogCreateSerializer,
        'update': serializer.BlogCreateSerializer,
        'retrieve': serializer.BlogUpdateSerializer,
        'get_values_for_update': serializer.BlogDataTableSerializer
    }
    # permission_classes = (IsAuthenticated,)
    # authentication_classes = (TokenAuthentication, SessionAuthentication)
    queryset = Entry.objects.all()
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ['title', 'author', ]  # for the global search
    filterset_class = BlogFilterSet
    ordering_fields = ['title', 'author', 'categories', 'published_timestamp']
    ordering = ('-title',)  # default order
    operation_type = ''
