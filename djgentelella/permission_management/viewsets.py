from django.shortcuts import get_object_or_404
from rest_framework import generics
from djgentelella.models import PermissionRelated
from djgentelella.permission_management.serializers import PermissionRelatedSerializer
from django.http import Http404

class PermissionRelatedDetailView(generics.RetrieveAPIView):
    queryset = PermissionRelated.objects.all()
    serializer_class = PermissionRelatedSerializer

    def get_object(self):
        permission_id = self.kwargs['permission_id']
        return get_object_or_404(PermissionRelated, main_permission_id=permission_id)
