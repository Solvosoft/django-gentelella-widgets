from datetime import timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.paginator import Paginator
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from djgentelella.flows.base import current_site, flow_for_instance, get_flow
from djgentelella.flows.diagram import render_svg
from djgentelella.flows.exceptions import TaskNotAllowed, TransitionNotAllowed
from djgentelella.flows.models import FlowInstance, Task
from djgentelella.flows.utils import json_safe
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as genwidgets


class CommentForm(GTForm):
    comment = forms.CharField(label=_('Comment'), required=False,
                              widget=genwidgets.Textarea(attrs={'rows': 3}))


class ReassignForm(GTForm):
    to_user = forms.ModelChoiceField(
        label=_('User'), required=False, widget=genwidgets.Select,
        queryset=get_user_model().objects.filter(is_active=True))
    to_group = forms.ModelChoiceField(label=_('Group'), required=False,
                                      widget=genwidgets.Select,
                                      queryset=Group.objects.all())
    comment = forms.CharField(label=_('Comment'), required=False,
                              widget=genwidgets.Textarea(attrs={'rows': 3}))


def flow_or_404(name, request=None):
    flow = get_flow(name, site=current_site(request))
    if flow is None:
        raise Http404()
    return flow


def to_pk(flow, pk):
    """``pk`` as the model's key, or Http404 when it cannot hold it
    ('abc' for an integer, a broken UUID)."""
    try:
        return flow.model._meta.pk.to_python(pk)
    except (ValidationError, ValueError):
        raise Http404() from None


def object_or_404(flow, request, pk):
    # get_queryset() is the flow's authorization rule for reaching an object:
    # anything outside it is a 404, which does not reveal it exists.
    return get_object_or_404(flow.get_queryset(request.user), pk=to_pk(flow, pk))


def detail_url(flow, obj):
    return reverse('flow_detail', args=[flow.name, obj.pk])


def refuse(request, flow, obj, reason):
    messages.error(request, reason)
    return HttpResponseRedirect(detail_url(flow, obj))


def safe_next(request, default):
    target = request.POST.get('next') or request.GET.get('next')
    if target and url_has_allowed_host_and_scheme(
            target, allowed_hosts={request.get_host()},
            require_https=request.is_secure()):
        return target
    return default


@login_required
def flow_detail(request, flow, pk):
    flow = flow_or_404(flow, request)
    obj = object_or_404(flow, request, pk)
    flow, instance = flow._bound(obj)
    state = instance.state if instance else flow.initial
    buttons = flow.transition_buttons(obj, request.user)
    return render(request, 'gentelella/flows/detail.html', {
        'flow': flow, 'object': obj, 'state': state, 'instance': instance,
        'state_label': flow.state_label(state),
        'overdue': bool(instance and instance.due_at
                        and instance.due_at <= timezone.now()),
        'transitions': buttons,
        'tokens': [{'label': flow.state_label(token['activity']), **token}
                   for token in (instance.tokens if instance else [])],
        'tasks': flow.tasks(obj).prefetch_related('potential_owners', 'groups')
        .select_related('actual_owner'),
        'control': control_actions(flow, instance, request.user),
        'assignment': flow.assignment_actions(obj, request.user),
        'history': flow.history(obj),
        'diagram': flow.instance_diagram(obj, request.user),
    })


@login_required
def flow_transition(request, flow, pk, transition):
    flow = flow_or_404(flow, request)
    obj = object_or_404(flow, request, pk)
    flow, _instance = flow._bound(obj)
    step = flow.get_transition(transition)
    if step is None or step.auto:
        raise Http404()
    ok, reason = flow.check(step, obj, request.user)
    if not ok:
        return refuse(request, flow, obj, reason or _(
            '%(transition)s is not available for %(object)s now.') % {
            'transition': step.label, 'object': obj})
    detail = detail_url(flow, obj)
    form_class = step.form
    form_kwargs = {'prefix': 'flow'}
    if form_class is not None and issubclass(form_class, forms.ModelForm):
        form_kwargs['instance'] = obj
    data = request.POST if request.method == 'POST' else None
    files = request.FILES if request.method == 'POST' else None
    form = form_class(data, files, **form_kwargs) if form_class else None
    comment = CommentForm(data, prefix='flow_comment')
    if request.method == 'POST' and comment.is_valid() and (
            form is None or form.is_valid()):
        try:
            instance = flow.run(obj, step.name, request.user, form=form,
                                comment=comment.cleaned_data['comment'],
                                request=request)
        except TransitionNotAllowed as error:
            # Someone else moved the object first, or an action refused.
            return refuse(request, flow, obj, str(error) or _(
                '%(transition)s could not run.') % {'transition': step.label})
        if instance.status == FlowInstance.ERROR:
            messages.warning(request, _('%(object)s: %(transition)s done, but the '
                                        'flow stopped on an error: %(error)s') % {
                'object': obj, 'transition': step.label, 'error': instance.error})
        else:
            messages.success(request, _('%(object)s: %(transition)s done.') % {
                'object': obj, 'transition': step.label})
        return HttpResponseRedirect(safe_next(request, detail))
    return render(request, 'gentelella/flows/transition.html', {
        'flow': flow, 'object': obj, 'transition': step, 'form': form,
        'comment_form': comment, 'state_label': flow.state_label(flow.state(obj)),
        'target_label': flow.state_label(step.target), 'detail_url': detail,
        'next': safe_next(request, ''),
    })


@login_required
def flow_assign(request, flow, action, pk):
    """Claim or release (POST), or reassign (through a form) the object."""
    flow = flow_or_404(flow, request)
    obj = object_or_404(flow, request, pk)
    if action not in ('claim', 'release', 'reassign'):
        raise Http404()
    detail = detail_url(flow, obj)
    form = None
    if action == 'reassign':
        if not flow.can_reassign(request.user):
            return refuse(request, flow, obj, _('You cannot reassign it.'))
        form = ReassignForm(request.POST if request.method == 'POST' else None,
                            prefix='flow_assign')
        if request.method != 'POST' or not form.is_valid():
            return render(request, 'gentelella/flows/assign.html', {
                'flow': flow, 'object': obj, 'form': form, 'detail_url': detail})
    elif request.method != 'POST':
        return HttpResponseRedirect(detail)
    try:
        if action == 'claim':
            flow.claim(obj, request.user)
        elif action == 'release':
            flow.release(obj, request.user)
        else:
            flow.reassign(obj, request.user, comment=form.cleaned_data['comment'],
                          to_user=form.cleaned_data['to_user'],
                          to_group=form.cleaned_data['to_group'])
    except TransitionNotAllowed as error:
        return refuse(request, flow, obj, str(error))
    messages.success(request, _('%(object)s: assignment updated.') % {'object': obj})
    return HttpResponseRedirect(safe_next(request, detail))


@login_required
@require_POST
def flow_bulk(request, flow):
    """Run one transition on the objects ticked in the inbox."""
    flow = flow_or_404(flow, request)
    inbox = reverse('flow_inbox', args=[flow.name])
    keys = []
    for pk in request.POST.getlist('objects'):
        try:
            keys.append(flow.model._meta.pk.to_python(pk))
        except (ValidationError, ValueError):
            continue
    # Only what the user may reach: other pks are dropped, not refused.
    objects = flow.get_queryset(request.user).filter(pk__in=keys)
    try:
        result = flow.run_many(objects, request.POST.get('transition', ''),
                               request.user, comment=request.POST.get('comment', ''))
    except TransitionNotAllowed as error:
        messages.error(request, str(error))
        return HttpResponseRedirect(safe_next(request, inbox))
    if result.done:
        messages.success(request, _('Done for %(count)d.') % {
            'count': len(result.done)})
    for obj, reason in result.refused:
        messages.warning(request, '%s: %s' % (obj, reason))
    if not result.done and not result.refused:
        messages.info(request, _('Nothing was selected.'))
    return HttpResponseRedirect(safe_next(request, inbox))


@login_required
def flow_inbox(request, flow):
    flow = flow_or_404(flow, request)
    queryset = flow.inbox(request.user)
    now = timezone.now()
    overdue = request.GET.get('overdue') == '1'
    if overdue:
        queryset = queryset.filter(flow_due_at__lte=now)
    page = Paginator(queryset.order_by('-pk'), 25).get_page(request.GET.get('page'))
    rows = [{'object': obj, 'state': flow.state_label(obj.flow_state),
             'due_at': obj.flow_due_at,
             'overdue': bool(obj.flow_due_at and obj.flow_due_at <= now),
             'url': detail_url(flow, obj)}
            for obj in page]
    return render(request, 'gentelella/flows/inbox.html', {
        'flow': flow, 'rows': rows, 'page': page, 'overdue': overdue,
        'bulk_transitions': flow.bulk_transitions(request.user),
    })


@login_required
def flow_diagram(request, flow):
    flow = flow_or_404(flow, request)
    graph = flow.as_graph()
    if request.GET.get('format') == 'json':
        return JsonResponse(graph)
    return render(request, 'gentelella/flows/diagram.html', {
        'flow': flow, 'diagram': render_svg(graph)})


# -- instance control -------------------------------------------------------------
CONTROL_LABELS = {'suspend': _('Suspend'), 'resume': _('Resume'),
                  'terminate': _('Terminate'), 'retry': _('Retry')}


def control_actions(flow, instance, user):
    """The control buttons ``user`` gets for ``instance``."""
    if instance is None or not flow.can_control(user):
        return []
    status = instance.status
    found = []
    if status in (FlowInstance.RUNNING, FlowInstance.ERROR):
        found.append('suspend')
    if status == FlowInstance.SUSPENDED:
        found.append('resume')
    if status == FlowInstance.ERROR:
        found.append('retry')
    if status not in (FlowInstance.COMPLETED, FlowInstance.TERMINATED):
        found.append('terminate')
    return [(action, CONTROL_LABELS[action]) for action in found]


@login_required
@require_POST
def flow_control(request, flow, action, pk):
    """Suspend, resume, terminate or retry an instance."""
    flow = flow_or_404(flow, request)
    obj = object_or_404(flow, request, pk)
    if action not in CONTROL_LABELS:
        raise Http404()
    if not flow.can_control(request.user):
        return refuse(request, flow, obj, _('You cannot control this flow.'))
    try:
        getattr(flow, action)(obj, request.user,
                              comment=request.POST.get('comment', ''))
    except TransitionNotAllowed as error:
        return refuse(request, flow, obj, str(error))
    messages.success(request, _('%(object)s: %(action)s done.') % {
        'object': obj, 'action': CONTROL_LABELS[action]})
    return HttpResponseRedirect(safe_next(request, detail_url(flow, obj)))


# -- the task inbox ---------------------------------------------------------------
class DelegateForm(GTForm):
    to_user = forms.ModelChoiceField(
        label=_('User'), widget=genwidgets.Select,
        queryset=get_user_model().objects.filter(is_active=True))
    comment = forms.CharField(label=_('Comment'), required=False,
                              widget=genwidgets.Textarea(attrs={'rows': 2}))


class RequestInfoForm(DelegateForm):
    comment = forms.CharField(label=_('What do you need to know?'),
                              widget=genwidgets.Textarea(attrs={'rows': 2}))


class InfoForm(GTForm):
    comment = forms.CharField(label=_('Answer'),
                              widget=genwidgets.Textarea(attrs={'rows': 2}))


class CompleteForm(GTForm):
    comment = forms.CharField(label=_('Comment'), required=False,
                              widget=genwidgets.Textarea(attrs={'rows': 2}))


class TaskCommentForm(GTForm):
    text = forms.CharField(label=_('Comment'),
                           widget=genwidgets.Textarea(attrs={'rows': 2}))


TASK_FORMS = {'delegate': DelegateForm, 'request_info': RequestInfoForm,
              'submit_info': InfoForm, 'complete': CompleteForm,
              'comment': TaskCommentForm}
DUE_FILTERS = [('overdue', _('Overdue')), ('today', _('Due today')),
               ('week', _('Due this week')), ('none', _('No due date'))]
STATE_FILTERS = [('open', _('Open'))] + list(Task.STATES) + [('all', _('All'))]


def filter_tasks(queryset, params, now=None):
    """The task inbox filters: ``flow``, ``priority``, ``state`` (``open`` by
    default, ``all``, or one state) and ``due`` (``overdue``, ``today``,
    ``week``, ``none``)."""
    now = now or timezone.now()
    state = params.get('state') or 'open'
    if state == 'open':
        queryset = queryset.filter(state__in=Task.OPEN)
    elif state != 'all':
        queryset = queryset.filter(state=state)
    if params.get('flow'):
        queryset = queryset.filter(instance__flow=params['flow'])
    if (params.get('priority') or '').isdigit():
        queryset = queryset.filter(priority=int(params['priority']))
    due = params.get('due')
    if due == 'overdue':
        queryset = queryset.filter(due__lte=now)
    elif due == 'today':
        queryset = queryset.filter(due__date=timezone.localdate(now))
    elif due == 'week':
        queryset = queryset.filter(due__lte=now + timedelta(days=7))
    elif due == 'none':
        queryset = queryset.filter(due__isnull=True)
    return queryset


def visible_tasks(user):
    """The tasks of the user and of their groups; everything with
    ``gtflows.view_task``."""
    if user.has_perm('gtflows.view_task'):
        return Task.objects.all()
    return Task.objects.for_user(user)


@login_required
def task_inbox(request):
    """Every task waiting for the user, of any flow (or of none)."""
    base = visible_tasks(request.user)
    queryset = filter_tasks(base, request.GET).select_related(
        'instance', 'actual_owner', 'content_type')
    page = Paginator(queryset, 25).get_page(request.GET.get('page'))
    flows = sorted(set(base.exclude(instance=None).values_list(
        'instance__flow', flat=True)))
    query = request.GET.copy()
    query.pop('page', None)
    return render(request, 'gentelella/flows/tasks/inbox.html', {
        'page': page, 'tasks': page.object_list, 'flows': flows,
        'priorities': Task.PRIORITIES, 'states': STATE_FILTERS,
        'dues': DUE_FILTERS, 'filters': request.GET, 'query': query.urlencode(),
        'now': timezone.now(),
    })


def task_or_404(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if not task.can_view(request.user):
        raise Http404()  # does not reveal the task exists
    return task


#: The prefix of a human task's own form on the task page.
TASK_FORM_PREFIX = 'task'


def task_form_class(task):
    """The form the ``human_task`` activity of ``task`` declares, or None
    (a task that stands alone, or whose flow has no form for it)."""
    if not task.instance_id or not task.activity:
        return None
    try:
        flow = flow_for_instance(task.instance)
    except ImproperlyConfigured:
        return None
    return getattr(flow.activities.get(task.activity), 'form', None)


def task_form(task, data=None):
    """The human task's form, bound to ``data`` (a POST) or with the instance
    variables of its fields as initial values; None when it has none."""
    form_class = task_form_class(task)
    if form_class is None:
        return None
    variables = task.instance.variables or {}
    initial = {name: variables[name] for name in form_class.base_fields
               if name in variables}
    return form_class(data, prefix=TASK_FORM_PREFIX, initial=initial)


def render_task(request, task, bound=None, status=200):
    allowed = task.allowed_actions(request.user)
    bound = bound or {}
    flow = None
    if task.instance_id:
        flow = get_flow(task.instance.flow, site=current_site(request))
    page_forms = {action: bound.get(action) or form(prefix=action)
                  for action, form in TASK_FORMS.items() if action in allowed}
    own_form = None
    if 'complete' in allowed:
        own_form = bound.get('task') or task_form(task)
    return render(request, 'gentelella/flows/tasks/detail.html', {
        'task': task, 'allowed': allowed, 'flow': flow,
        'object': task.content_object,
        'forms': page_forms, 'task_form': own_form,
        'history': task.history.select_related('user', 'to_user'),
        'comments': task.comments.select_related('user'),
    }, status=status)


@login_required
def task_detail(request, pk):
    return render_task(request, task_or_404(request, pk))


@login_required
@require_POST
def task_action(request, pk, action):
    """Claim, release, delegate, request or submit information, complete or
    comment a task (POST)."""
    task = task_or_404(request, pk)
    detail = reverse('task_detail', args=[task.pk])
    form_class = TASK_FORMS.get(action)
    form = form_class(request.POST, prefix=action) if form_class else None
    if form is not None and not form.is_valid():
        messages.error(request, '; '.join(
            '%s: %s' % (form.fields[name].label if name in form.fields else name,
                        ' '.join(errors)) for name, errors in form.errors.items()))
        return HttpResponseRedirect(detail)
    data = form.cleaned_data if form is not None else {}
    user = request.user
    task_data = None
    if action == 'complete' and task.can(user, 'complete'):
        own_form = task_form(task, request.POST)
        if own_form is not None:
            if not own_form.is_valid():
                messages.error(request, _('Check the form of the task.'))
                return render_task(request, task, {'task': own_form,
                                                   'complete': form}, status=400)
            task_data = json_safe(own_form.cleaned_data)
    try:
        if action == 'claim':
            task.claim(user)
        elif action == 'release':
            task.release(user)
        elif action == 'delegate':
            task.delegate(user, data['to_user'], data['comment'])
        elif action == 'request_info':
            task.request_info(user, data['to_user'], data['comment'])
        elif action == 'submit_info':
            task.submit_info(user, data['comment'])
        elif action == 'complete':
            task.complete(user, request.POST.get('outcome', ''), data['comment'],
                          data=task_data)
        elif action == 'comment':
            task.comment(user, data['text'])
        else:
            raise Http404()
    except (TaskNotAllowed, TransitionNotAllowed) as error:
        messages.error(request, str(error))
        return HttpResponseRedirect(detail)
    messages.success(request, _('%(task)s: %(action)s.') % {
        'task': task, 'action': Task.action_label(action)})
    if action in ('complete', 'release', 'delegate'):
        return HttpResponseRedirect(safe_next(request, reverse('task_inbox')))
    return HttpResponseRedirect(safe_next(request, detail))
