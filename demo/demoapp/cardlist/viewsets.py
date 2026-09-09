from django.utils.translation import gettext_lazy as _
from rest_framework import mixins

from djgentelella.views.listAreaViewset import ListAreaViewset
from .filterset import PersonCardListFilterSet
from .forms import CardListPerson
from .serializer import (
    PersonCardSerializer,
    PersonCardUpdateValuesSerializer,
    PersonCreateSerializer,
    PersonUpdateSerializer,
)
from ..models import Person


class PersonCardListViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin,
                            mixins.UpdateModelMixin, mixins.DestroyModelMixin,
                            ListAreaViewset):
    serializer_class = PersonCardSerializer
    queryset = Person.objects.all()
    search_fields = ['name', 'num_children']
    filterset_class = PersonCardListFilterSet
    filter_form = CardListPerson
    ordering_fields = ['name', 'num_children', 'born_date', 'last_time']
    ordering = ('-num_children',)
    html_id = 'cardListContainer'
    template_name = 'gentelella/cardlist/person_list.html'
    extra_template_context = {'card_col_class': 'col col-md-4 p-2'}
    distribution_value = '2/1p'

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        return queryset

    def get_serializer_class(self):
        if self.action == 'create':
            return PersonCreateSerializer
        if self.action == 'retrieve':
            return PersonCardUpdateValuesSerializer
        if self.action in ('update', 'partial_update'):
            return PersonUpdateSerializer
        return super().get_serializer_class()

    def get_actions(self):
        return [{
            'name': 'add',
            'icon': 'fa fa-plus',
            'title': _('Add person'),
            'class': 'btn-outline-success'
        }]
