from django import template
from django.urls import NoReverseMatch, reverse
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _

from djgentelella.flows.base import current_site, get_flow
from djgentelella.flows.diagram import render_svg
from djgentelella.flows.models import Task

register = template.Library()


def _flow(context, flow_name):
    return get_flow(flow_name, site=current_site(context.get('request')))


@register.inclusion_tag('gentelella/flows/status.html', takes_context=True)
def flow_status(context, obj, flow_name):
    """The state of ``obj`` in a flow and the transitions the user may run
    (or could, disabled with the reason, when only the condition fails).

    ``{% load gtflows %}{% flow_status object 'app.ReviewFlow' %}``
    """
    flow = _flow(context, flow_name)
    if flow is None:
        return {'flow': None}
    request = context.get('request')
    user = getattr(request, 'user', None)
    flow, instance = flow._bound(obj)
    state = instance.state if instance else flow.initial
    try:
        detail_url = reverse('flow_detail', args=[flow.name, obj.pk])
    except NoReverseMatch:  # the project did not include djgentelella's URLs
        detail_url = ''
    return {
        'flow': flow, 'object': obj, 'state_label': flow.state_label(state),
        'instance': instance, 'final': flow.is_final(state),
        'transitions': ((flow.transition_buttons(obj, user) if user else [])
                        if detail_url else []),
        'detail_url': detail_url,
        'next': request.get_full_path() if request else '',
    }


@register.simple_tag(takes_context=True)
def flow_states(context, objects, flow_name):
    """``{pk: state label}`` for a list of objects, in one query.

    ``{% flow_states objects 'app.Flow' as states %}`` then
    ``{{ states|flow_label:object.pk }}``.
    """
    flow = _flow(context, flow_name)
    if flow is None:
        return {}
    return {pk: flow.state_label(state)
            for pk, state in flow.states_for(objects).items()}


@register.filter
def flow_label(states, pk):
    return states.get(pk, '')


@register.simple_tag(takes_context=True)
def flow_diagram(context, flow_name, obj=None):
    """The flow as an SVG; with ``obj``, its activities under way, done and
    failed are highlighted.

    ``{% flow_diagram 'app.Flow' object %}``
    """
    flow = _flow(context, flow_name)
    if flow is None:
        return ''
    if obj is None:
        return render_svg(flow.as_graph())
    flow, instance = flow._bound(obj)
    return render_svg(flow.as_graph(), runtime=flow.runtime(instance))


@register.simple_tag(takes_context=True)
def task_inbox_count(context):
    """How many open tasks the user can see or take: ``{% task_inbox_count %}``."""
    request = context.get('request')
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return 0
    return Task.objects.inbox(user).count()


#: Labels of the outcomes a task has by default; any other is shown as it is.
OUTCOME_LABELS = {'approve': _('Approve'), 'reject': _('Reject'),
                  'expired': _('Expired')}


@register.filter
def outcome_label(outcome):
    """``{{ task.outcome|outcome_label }}``: the translated label of an
    outcome."""
    return OUTCOME_LABELS.get(outcome) or capfirst(outcome)
