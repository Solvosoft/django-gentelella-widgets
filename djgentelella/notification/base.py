from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView
from rest_framework.viewsets import GenericViewSet

from djgentelella.models import Notification
from djgentelella.notification.serializer import NotificationSerializer, NotificationPagination, \
    NotificationSerializerUpdate

from rest_framework import mixins, permissions


class NotificacionAPIView( mixins.RetrieveModelMixin,
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


@method_decorator(login_required, name='dispatch')
class NotificationList(ListView):
    model = Notification
    template_name = 'gentelella/menu/notification_list.html'

    def get_queryset(self):
        queryset = super(NotificationList, self).get_queryset()
        queryset = queryset.filter(user=self.request.user).order_by('state', 'creation_date')
        return queryset