from collections import OrderedDict

from django.db.models import Q
from rest_framework import generics
from rest_framework import serializers
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from djgentelella.designs.exposure import request_site, site_field_of
from djgentelella.sites import site_q

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
            ('pagination', {'more': self.page.has_next()}),
            ('results', data)
        ]))


class GSerializerBase(serializers.Serializer):
    def get_id(self, obj) -> int | str:
        return self.view.get_id_display(obj)

    def get_text(self, obj) -> str:
        return self.view.get_text_display(obj)

    def get_selected(self, obj) -> bool:
        return self.view.get_selected_display(obj)

    def get_disabled(self, obj) -> bool:
        return self.view.get_disabled_display(obj)

    id = serializers.SerializerMethodField()
    text = serializers.SerializerMethodField()
    disabled = serializers.SerializerMethodField()
    selected = serializers.SerializerMethodField()


class GSerializerImgBase(serializers.Serializer):
    def get_id(self, obj) -> int | str:
        return self.view.get_id_display(obj)

    def get_text(self, obj) -> str:
        return self.view.get_text_display(obj)

    def get_url(self, obj) -> str:
        return self.view.get_url(obj)

    def get_selected(self, obj) -> bool:
        return self.view.get_selected_display(obj)

    def get_disabled(self, obj) -> bool:
        return self.view.get_disabled_display(obj)

    id = serializers.SerializerMethodField()
    text = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()
    disabled = serializers.SerializerMethodField()
    selected = serializers.SerializerMethodField()


class ViewFromContext:
    """``self.view``: the view the serializer serves, from the context DRF
    gives every serializer it builds (``get_serializer``)."""

    @property
    def view(self):
        return self.context.get('view')


# One ModelSerializer per (view class, model, base serializer), built on the
# first request: a class per request made DRF inspect the model's fields anew
# every time.
_serializer_classes = {}


def model_serializer_class(view, fields):
    """The ModelSerializer of ``view.model`` on ``view.serializer_class``."""
    key = (type(view), view.model, view.serializer_class, tuple(fields))
    serializer_class = _serializer_classes.get(key)
    if serializer_class is None:
        meta = type('Meta', (), {'model': view.model, 'fields': list(fields)})
        serializer_class = type(
            'S', (ViewFromContext, view.serializer_class, serializers.ModelSerializer),
            {'Meta': meta, '__module__': __name__})
        _serializer_classes[key] = serializer_class
    return serializer_class


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
    # Opt-in: drop the rows the widget says it already has selected instead of
    # returning them flagged. The javascript hides them anyway, but it can only
    # hide what is inside the page it received -- with the default page size a
    # page whose five rows are all selected reaches the browser and leaves the
    # dropdown looking empty. Excluding them here keeps every page full.
    exclude_selected = False
    #: The foreign key to ``sites.Site`` the rows are limited by: those of
    #: the request's Site and the global ones. ``None`` (the default) takes
    #: the ``site_field`` the model was exposed to designs with
    #: (:func:`djgentelella.designs.exposure.expose`); ``''`` turns it off.
    site_field = None

    def get_site_field(self):
        if self.site_field is not None:
            return self.site_field
        return site_field_of(getattr(self, 'model', None))

    def filter_site(self, queryset):
        """The rows of the request's Site and the global ones, when the lookup
        has a :attr:`site_field`."""
        name = self.get_site_field()
        if not name:
            return queryset
        return queryset.filter(site_q(request_site(self.request), field=name))

    def get_filter_suffix(self, fieldname):
        if hasattr(self, f'get_filter_suffix_{fieldname}'):
            return getattr(self, f'get_filter_suffix_{fieldname}')()
        return '__icontains'

    def filter_data(self, queryset, qe):
        filters = None
        for field in self.fields:
            suffix = self.get_filter_suffix(field)
            for q in qe:
                if filters is None:
                    filters = Q(**{field + suffix: q})
                else:
                    filters |= Q(**{field + suffix: q})
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
        queryset = self.filter_site(queryset)
        q = self.query_get('term', '')
        if hasattr(self, 'selected'):
            self.selected += self.query_get('selected', '')
        else:
            self.selected = self.query_get('selected', '')
        if self.ref_field is not None:
            relq = self.query_get(self.ref_name, '')
            if relq:
                queryset = queryset.filter(**{self.ref_field + '__in': relq})
            else:
                queryset = queryset.none()

        if q and self.fields:
            queryset = self.filter_data(queryset, q)
        if self.exclude_selected and self.selected:
            queryset = queryset.exclude(**{f'{self.id_field}__in': self.selected})
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
        return model_serializer_class(self, ['id', 'text', 'disabled', 'selected'])

    def get_field_value(self, obj, name, func=None):
        if name == '__str__':
            return str(obj)

        dev = getattr(obj, name)
        if func is not None:
            dev = func(dev)
        if self.text_wrapper:
            dev = self.text_wrapper % dev
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

    def get_selected(self, obj) -> bool:
        return self.view.get_selected_display(obj)

    def get_disabled_display(self, obj):
        return False


class BaseSelectImg2View(BaseSelect2View):
    model = None
    fields = []
    pagination_class = GPaginator
    serializer_class = GSerializerImgBase

    def get_serializer_class(self):
        return model_serializer_class(
            self, ['id', 'text', 'url', 'disabled', 'selected'])
