from django_filters import DateFromToRangeFilter, DateTimeFromToRangeFilter
from django_filters import FilterSet

from demoapp.models import Person
from djgentelella.fields.drfdatetime import DateRangeTextWidget, DateTimeRangeTextWidget


class PersonFilterSet(FilterSet):
    born_date = DateFromToRangeFilter(
        widget=DateRangeTextWidget(attrs={'placeholder': 'YYYY/MM/DD'}))
    last_time = DateTimeFromToRangeFilter(
        widget=DateTimeRangeTextWidget(attrs={'placeholder': 'YYYY/MM/DD HH:MM:SS'}))

    class Meta:
        model = Person
        fields = {'name': ['icontains'], 'num_children': ['exact'],
                  'country__name': ['icontains']}
