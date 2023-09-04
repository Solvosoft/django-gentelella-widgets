from rest_framework import generics
from djgentelella.models import PermissionRelated
from djgentelella.permission_management.serializers import PermissionRelatedSerializer
from django.http import Http404

class PermissionRelatedDetailView(generics.RetrieveAPIView):
    queryset = PermissionRelated.objects.all()  # Esto selecciona todos los objetos PermissionRelated
    serializer_class = PermissionRelatedSerializer

    def get_object(self):
        permission_id = self.kwargs['permission_id']
        try:
            # Obtén el objeto PermissionRelated relacionado con el permiso principal
            # especificado por permission_id
            return PermissionRelated.objects.get(main_permission_id=permission_id)
        except PermissionRelated.DoesNotExist:
            raise Http404
