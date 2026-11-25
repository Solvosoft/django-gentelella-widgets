from django import template
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import NoReverseMatch, reverse
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _

from djgentelella.flows.base import current_site, get_flow, get_flows
from djgentelella.flows.models import FlowInstance, Task

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


def flow_of_object(obj, site=None):
    """The flow ``obj`` runs in: the one of its most recent instance, else
    the only flow (declared or published) over its model; ``None`` when
    there is none or more than one could be meant."""
    content_type = ContentType.objects.get_for_model(type(obj))
    keys = {str(obj.pk)}
    if hasattr(obj.pk, 'hex'):
        keys.add(obj.pk.hex)
    name = FlowInstance.objects.filter(
        content_type=content_type, object_id__in=keys).order_by(
        '-updated_at', '-pk').values_list('flow', flat=True).first()
    if name is not None:
        return get_flow(name, site=site)
    found = [flow for flow in get_flows().values() if flow.model is type(obj)]
    if len(found) == 1:
        return get_flow(found[0].name, site=site) or found[0]
    return None


@register.simple_tag(takes_context=True)
def flow_diagram(context, flow_or_object, obj=None, flow=None):
    """The flow as an SVG. With an object, the instance's diagram: its
    current activity, the way it took and the transitions the user may run
    now are highlighted, and the image says so in its ``<title>``/``<desc>``.

    ``{% flow_diagram object %}`` finds the flow of the object (that of its
    instance, else the only flow over its model); ``{% flow_diagram object
    flow='app.Flow' %}`` or ``{% flow_diagram 'app.Flow' object %}`` names it;
    ``{% flow_diagram 'app.Flow' %}`` draws the bare flow.
    """
    request = context.get('request')
    site = current_site(request)
    if isinstance(flow_or_object, models.Model):
        obj = flow_or_object
        found = (get_flow(flow, site=site) if flow
                 else flow_of_object(obj, site=site))
    else:
        found = _flow(context, flow_or_object)
    if found is None:
        return ''
    return found.instance_diagram(obj, getattr(request, 'user', None))


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
