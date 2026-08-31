import json

from django.contrib.admin.models import LogEntry
from django_filters.rest_framework import CharFilter, ChoiceFilter, FilterSet
from django_filters import DateTimeFromToRangeFilter
from djgentelella.fields.drfdatetime import DateTimeRangeTextWidget
from djgentelella.history.utils import ACTIONS


class HistoryFilterSet(FilterSet):
    action_time = DateTimeFromToRangeFilter(
        widget=DateTimeRangeTextWidget(attrs={'placeholder': 'DD/MM/YYYY/'})
    )

    action_flag = ChoiceFilter(
        field_name='action_flag',
        choices=[(k, str(v)) for k, v in ACTIONS.items()],  # added 4 y 5
    )

    # ?extra={"key": "value", ...} — entries whose HistoryRelation data
    # contains every given key/value pair.
    extra = CharFilter(method='filter_extra')

    def filter_extra(self, queryset, name, value):
        """Filter by 1..n keys of the relations' JSON payload.

        All the pairs must match on the SAME relation row, hence the single
        ``filter()`` call.  Built as chained key lookups instead of
        ``data__contains`` because SQLite (where the library's tests run)
        does not implement JSONField containment.
        """
        try:
            wanted = json.loads(value)
        except (TypeError, ValueError):
            return queryset.none()
        if not isinstance(wanted, dict) or not wanted:
            return queryset.none()
        lookups = {
            'gt_relations__data__%s' % key: val for key, val in wanted.items()
        }
        return queryset.filter(**lookups).distinct()

    class Meta:
        model = LogEntry
        fields = {
            'object_repr': ['icontains'],
            'change_message': ['icontains'],
            'user': ['exact'],
        }
