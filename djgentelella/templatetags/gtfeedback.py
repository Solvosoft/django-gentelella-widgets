"""``{% gt_feedback_button %}``: the feedback button and its modal
(:mod:`djgentelella.feedback`)."""

from django import template
from django.urls import NoReverseMatch, reverse

from djgentelella.feedback.conf import feedback_enabled
from djgentelella.feedback.forms import FeedbackForm

register = template.Library()


@register.inclusion_tag('gentelella/feedback/button.html', takes_context=True)
def gt_feedback_button(context):
    request = context.get('request')
    if not feedback_enabled(request):
        return {'enabled': False}
    try:
        url = reverse('gt_feedback_create')
    except NoReverseMatch:  # the project did not include djgentelella's URLs
        return {'enabled': False}
    return {'enabled': True, 'url': url, 'form': FeedbackForm(prefix='gtfeedback'),
            'next': request.get_full_path(), 'request': request}
