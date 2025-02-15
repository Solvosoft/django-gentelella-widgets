from djgentelella.views.listAreaViewset import ListAreaViewset
from .filterset import PersonCardListFilterSet
from .forms import CardListPerson
from .serializer import PersonCardSerializer
from ..models import Person


class PersonCardListViewSet(ListAreaViewset):
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

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        return queryset

    def get_actions(self):
        return [{
            'name': 'generalexample',
            'icon': 'fa fa-plus',
            'title': 'general of action',
            'class': 'btn-primary'
        }]
