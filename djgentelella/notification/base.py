from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework import mixins, permissions, viewsets
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response

from djgentelella.models import Notification
from djgentelella.notification.serializer import NotificationSerializer, \
    NotificationPagination, \
    NotificationSerializerUpdate, \
    NotificationDataTableSerializer,\
    NotificationFilterSet


@login_required
def notification_list_view(request):
    return render(request, 'gentelella/menu/notification_list.html')


class NotificacionAPIView(mixins.RetrieveModelMixin,
                          mixins.UpdateModelMixin,
                          mixins.DestroyModelMixin,
                          mixins.ListModelMixin,
                          GenericViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    pagination_class = NotificationPagination
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(user=self.request.user,
                               state='visible')

    def get_serializer_class(self):
        if self.request.method == 'PUT':
            return NotificationSerializerUpdate
        return super().get_serializer_class()


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationDataTableSerializer
    pagination_class = LimitOffsetPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ('description', 'message_type', 'state',)
    filterset_class = NotificationFilterSet
    ordering_fields = ['creation_date', 'message_type', 'description', 'link', 'state']
    ordering = ('-message_type',)

    def filter_queryset(self, queryset):
        return super().filter_queryset(queryset)

    def get_queryset(self):
        queryset = Notification.objects.filter(user=self.request.user)
        return queryset

    def list(self, request, *args, **kwargs):
        self.request = request
        queryset = self.filter_queryset(self.get_queryset())
        data = self.paginate_queryset(queryset)
        response = {'data': data, 'recordsTotal': Notification.objects.filter(
                    user=self.request.user).count(),
                    'recordsFiltered': queryset.count(),
                    'draw': self.request.GET.get('draw', 1)}

        return Response(self.get_serializer(response).data)
