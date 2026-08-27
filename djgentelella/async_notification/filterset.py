from django.db.models import Q
from django_filters import (
    CharFilter,
    FilterSet,
    DateFromToRangeFilter,
    DateTimeFromToRangeFilter,
)
from djgentelella.async_notification.models import (
    NewsLetter,
    NewsLetterTemplate,
    EmailTemplate,
    NewsLetterTask,
)
from djgentelella.fields.drfdatetime import DateRangeTextWidget, DateTimeRangeTextWidget


class NewsletterFilterSet(FilterSet):
    template__title = CharFilter(field_name='template__title', lookup_expr='icontains')
    created_by = CharFilter(method='filter_created_by')
    created_at = DateTimeFromToRangeFilter(
        widget=DateTimeRangeTextWidget(attrs={'placeholder': 'YYYY/MM/DD'})
    )

    class Meta:
        model = NewsLetter
        fields = {'subject': ['icontains'], 'created_at': ['icontains']}

    def filter_created_by(self, queryset, name, value):
        return queryset.filter(
            Q(created_by__username__icontains=value)
            | Q(created_by__first_name__icontains=value)
            | Q(create_by__last_name__icontains=value)
        )


class NewsletterTemplateFilterSet(FilterSet):
    created_at = DateTimeFromToRangeFilter(
        widget=DateTimeRangeTextWidget(attrs={'placeholder': 'YYYY/MM/DD'})
    )

    class Meta:
        model = NewsLetterTemplate
        fields = {
            'title': ['icontains'],
            'slug': ['icontains'],
            'model_base': ['icontains'],
        }


class EmailTemplateFilterSet(FilterSet):
    created_at = DateTimeFromToRangeFilter(
        widget=DateTimeRangeTextWidget(attrs={'placeholder': 'YYYY/MM/DD'})
    )

    class Meta:
        model = EmailTemplate
        fields = {'code': ['icontains'], 'subject': ['icontains']}


class NewsLetterTaskFilterSet(FilterSet):
    send_date = DateTimeFromToRangeFilter(
        widget=DateTimeRangeTextWidget(attrs={'placeholder': 'YYYY/MM/DD'})
    )
    created_at = DateTimeFromToRangeFilter(
        widget=DateTimeRangeTextWidget(attrs={'placeholder': 'YYYY/MM/DD'})
    )

    class Meta:
        model = NewsLetterTask
        fields = {'status': ['exact'], 'newsletter__subject': ['icontains']}
