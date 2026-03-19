from djgentelella.groute import register_lookups
from djgentelella.views.select2autocomplete import BaseSelect2View

from djgentelella.async_notification.models import (
    EmailTemplate, NewsLetterTemplate, NewsLetter
)


@register_lookups(prefix="emailtemplate",
                  basename="emailtemplatebasename")
class EmailTemplateSelect2View(BaseSelect2View):
    model = EmailTemplate
    fields = ['code', 'subject']
    order_by = '-created_at'

    def get_queryset(self):
        qs = super().get_queryset()
        exclude_pk = self.request.query_params.get('exclude', '').strip()
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        return qs


@register_lookups(prefix="newslettertemplate",
                  basename="newslettertemplatebasename")
class NewsLetterTemplateSelect2View(BaseSelect2View):
    model = NewsLetterTemplate
    fields = ['title']
    order_by = '-created_at'


@register_lookups(prefix="newsletter",
                  basename="newsletterbasename")
class NewsLetterSelect2View(BaseSelect2View):
    model = NewsLetter
    fields = ['subject']
    order_by = '-created_at'
