from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import LimitOffsetPagination
from djgentelella.blog.blog import BaseObjectBlog
from djgentelella.datatables import serializer
from djgentelella.datatables.serializer import BlogFilterSet
from djgentelella.blog.models import Entry


class ObjectBLog(BaseObjectBlog):
    serializer_class = {
        'list': serializer.BlogDataTableSerializer,
        'create': serializer.BlogCreateSerializer,
        'update': serializer.BlogCreateSerializer,
        'retrieve': serializer.BlogUpdateSerializer,
        'get_values_for_update': serializer.BlogUpdateSerializer
    }
    perms = {
        'list': ['blog.view_entry'],
        'create': ['blog.add_category', 'blog.add_entry', 'blog.add_entry_image'],
        'update': ['blog.change_category', 'blog.change_entry', 'blog.change_entry_image'],
        'retrieve': ['blog.view_entry', 'blog.view_category', 'blog.view_entry_image'],
        'get_values_for_update': ['blog.view_entry'],
        'destroy': ['blog.delete_entry_image', 'blog.delete_category', 'blog.delete_entry']
    }
    #Asigna el author al usuario actual
    def perform_create(self, serializer): # ESTO ASIGNA EL author
        serializer.save(author=self.request.user)
        self.operation_type = 'create'

    # permission_classes = (IsAuthenticated,)
    # authentication_classes = (TokenAuthentication, SessionAuthentication)
    queryset = Entry.objects.all()
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ['title', 'resume', 'content']   # for the global search
    filterset_class = BlogFilterSet
    ordering_fields = ['title', 'author', 'resume', 'content', 'categories']
    ordering = ('-title',)  # default order
    operation_type = ''
