from django.contrib.contenttypes.models import ContentType
from django_filters import DateTimeFromToRangeFilter
from django_filters.rest_framework import FilterSet
from djgentelella.fields.drfdatetime import DateTimeRangeTextWidget

from djgentelella.models import Trash


class TrashFilter(FilterSet):
    created_at = DateTimeFromToRangeFilter(
        widget=DateTimeRangeTextWidget(attrs={"placeholder": "DD/MM/YYYY/"})
    )

    class Meta:
        model = Trash
        fields = {
            'content_type__model': ['exact'],
            'object_id': ['exact'],
            'created_at': ['exact'],
        }
