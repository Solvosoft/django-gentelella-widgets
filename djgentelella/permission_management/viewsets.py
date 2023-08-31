from django.http import Http404
from rest_framework import generics

from djgentelella.models import PermissionRelated
from permission_management.serializers import PermissionRelatedSerializer


class PermissionRelatedViewset(generics.RetrieveAPIView, generics.GenericAPIView):
     queryset = PermissionRelated.objects.all()
     serializer_class = PermissionRelatedSerializer

     def get_object(self):
         obj = self.queryset.filter(main_permission=self.kwargs['pk']).first()
         if obj is None:
             raise Http404
         return obj




