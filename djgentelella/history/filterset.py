from django.contrib.admin.models import LogEntry
from django_filters.rest_framework import FilterSet, ChoiceFilter
from django_filters import DateTimeFromToRangeFilter
from djgentelella.fields.drfdatetime import DateTimeRangeTextWidget
from djgentelella.history.utils import ACTIONS

class HistoryFilterSet(FilterSet):
    action_time = DateTimeFromToRangeFilter(
        widget=DateTimeRangeTextWidget(attrs={"placeholder": "DD/MM/YYYY/"})
    )

    action_flag = ChoiceFilter(
        field_name="action_flag",
        choices=[(k, str(v)) for k, v in ACTIONS.items()],  # added 4 y 5
    )

    class Meta:
        model = LogEntry
        fields = {
            "object_repr": ["icontains"],
            "change_message": ["icontains"],
            "user": ["exact"],
        }
