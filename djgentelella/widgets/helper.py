from rest_framework import viewsets
from rest_framework import permissions

from djgentelella.models import Help
from djgentelella.serializers.helper import HelperSerializer


class HelperWidgetView(viewsets.ModelViewSet):
    serializer_class = HelperSerializer
    queryset = Help.objects.all()
    permission_classes = [permissions.IsAuthenticated,
                          permissions.DjangoModelPermissions
                          ]


    def get_queryset(self):
        queryset=super().get_queryset()
        id_view = self.request.GET.get('id_view', '')
        question_name  = self.request.GET.get('question_name', '')
        if id_view :
            queryset = queryset.filter(id_view=id_view)
        if question_name:
            queryset = queryset.filter(question_name=question_name)
        return queryset