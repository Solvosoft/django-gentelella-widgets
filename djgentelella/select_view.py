from collections import OrderedDict

from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework import generics
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

"""
{
  "results": [
    {
      "id": 1,
      "text": "Option 1",
      "selected": true
    },
    {
      "id": 2,
      "text": "Option 2",
      "disabled": true
      
    }
  ],
  "pagination": {
    "more": true
  }
}
"""

class GPaginator(PageNumberPagination):
    page_size = 10

    def get_paginated_response(self, data):
        more = {
            'more': self.display_page_controls
        }
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ("pagination", more),
            ('results', data)
        ]))


class GSerializerBase(serializers.Serializer):
    def get_id(self, obj):
        return self.view.get_id_display(obj)

    def get_text(self, obj):
        return self.view.get_text_display(obj)

    id = serializers.SerializerMethodField()
    text = serializers.SerializerMethodField()
    #disabled = serializers.BooleanField(source='get_disabled_display',default=False)
    #selected = serializers.BooleanField(source='get_selected_display', default=True)




class GModelLookup(generics.ListAPIView, viewsets.GenericViewSet):
    model = None
    fields = []
    pagination_class = GPaginator
    serializer_class = GSerializerBase
    id_field = 'pk'

    def filter_data(self, queryset, q):
        filters = None
        for field in self.fields:
            if filters is None:
                filters = Q(**{field + '__icontains': q})
            else:
                filters |= Q(**{field+'__icontains': q})
        return queryset.filter(filters)

    def filter_queryset(self, queryset):
        q=self.request.GET.get('q', '')
        if q and self.fields:
            queryset = self.filter_data(queryset, q)
        return queryset
    def get_queryset(self):
        assert self.model is not None, (
            "'%s' should either include a `model` attribute, "
            "or override the `get_queryset()` method."
            % self.__class__.__name__
        )
        return self.model.objects.all()

    # def get_serializer(self, *args, **kwargs):
    #     return super().get_serializer(self, *args, **kwargs)


    def get_serializer_class(self):
        class S(self.serializer_class, serializers.ModelSerializer):
            view = self
            class Meta:
                model = self.model
                fields = ['id', 'text']
        return S

    def get_field_value(self, obj, name, func=None):
        if name == '__str__':
            return str(obj)

        dev = getattr(obj, name)
        if func is not None:
            dev = func(dev)
        return dev

    def get_id_display(self, obj):
        return self.get_field_value(obj, self.id_field)

    def get_text_display(self, obj):
        if self.fields:
            fields = [self.get_field_value(obj, x, str) for x in self.fields]
            return " ".join(fields)
        return str(obj)