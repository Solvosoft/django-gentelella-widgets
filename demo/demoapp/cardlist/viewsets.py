from djgentelella.views.listAreaViewset import ListAreaViewset
from .filterset import PersonFilterSet
from .forms import CardListPerson
from .serializer import PersonSerializer
from ..models import Person


class PersonCardListViewSet(ListAreaViewset):
    serializer_class = PersonSerializer
    queryset = Person.objects.all()
    search_fields = ['name', 'num_children']
    filterset_class = PersonFilterSet
    filter_form = CardListPerson
    ordering_fields = ['name', 'num_children', 'born_date', 'last_time']
    ordering = ('-num_children',)
    html_id = 'cardListContainer'
    template_name = 'gentelella/cardlist/person_list.html'
