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
    page_size = 5

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('total_count', self.page.paginator.count),
            ("pagination", {'more': self.page.has_next()}),
            ('results', data)
        ]))


class GSerializerBase(serializers.Serializer):
    def get_id(self, obj):
        return self.view.get_id_display(obj)

    def get_text(self, obj):
        return self.view.get_text_display(obj)

    def get_selected(self, obj):
        return self.view.get_selected_display(obj)

    def get_disabled(self, obj):
        return self.view.get_disabled_display(obj)

    id = serializers.SerializerMethodField()
    text = serializers.SerializerMethodField()
    disabled = serializers.SerializerMethodField()
    selected = serializers.SerializerMethodField()


class BaseSelect2View(generics.ListAPIView, viewsets.GenericViewSet):
    model = None
    fields = []
    pagination_class = GPaginator
    serializer_class = GSerializerBase
    id_field = 'pk'
    ref_field = None
    ref_name = 'relfield'
    text_separator = ' '
    text_wrapper = ''
    order_by = 'pk'

    def filter_data(self, queryset, qe):
        filters = None
        for field in self.fields:
            for q in qe:
                if filters is None:
                    filters = Q(**{field + '__icontains': q})
                else:
                    filters |= Q(**{field + '__icontains': q})
        return queryset.filter(filters)

    def query_get(self, name, default, aslist=False):
        if aslist:
            q = self.request.GET.getlist(name, default)
        else:
            q = self.request.GET.get(name, default)
            if isinstance(q, str):
                q = q.split(',')
            if q == ['']:
                q = []
        return q


    def filter_queryset(self, queryset):
        q = self.query_get('term', '')
        self.selected = self.query_get('selected', '')
        if self.ref_field is not None:
            relq = self.query_get(self.ref_name, '')
            if relq:
                queryset = queryset.filter(**{self.ref_field+'__in': relq})
            else:
                queryset = queryset.none()

        if q and self.fields:
            queryset = self.filter_data(queryset, q)
        return queryset

    def get_queryset(self):
        assert self.model is not None, (
                "'%s' should either include a `model` attribute, "
                "or override the `get_queryset()` method."
                % self.__class__.__name__
        )
        return self.model.objects.all().order_by(self.order_by)

    # def get_serializer(self, *args, **kwargs):
    #     return super().get_serializer(self, *args, **kwargs)

    def get_serializer_class(self):
        class S(self.serializer_class, serializers.ModelSerializer):
            view = self

            class Meta:
                model = self.model
                fields = ['id', 'text', 'disabled', 'selected']

        return S

    def get_field_value(self, obj, name, func=None):
        if name == '__str__':
            return str(obj)

        dev = getattr(obj, name)
        if func is not None:
            dev = func(dev)
        if self.text_wrapper:
            dev = self.text_wrapper%dev
        return dev

    def get_id_display(self, obj):
        return self.get_field_value(obj, self.id_field)

    def get_text_display(self, obj):
        if self.fields:
            fields = [self.get_field_value(obj, x, str) for x in self.fields]
            return self.text_separator.join(fields)
        return str(obj)

    def get_selected_display(self, obj):
        iid = str(self.get_id_display(obj))
        return iid in self.selected

    def get_selected(self, obj):
        return self.view.get_selected_display(obj)

    def get_disabled_display(self, obj):
        return False