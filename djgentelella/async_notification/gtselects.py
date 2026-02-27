from djgentelella.groute import register_lookups
from djgentelella.views.select2autocomplete import BaseSelect2View

from djgentelella.async_notification.models import (
    NewsLetterTemplate, NewsLetter
)


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
