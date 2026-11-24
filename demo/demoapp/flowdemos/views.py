"""The flow demo pages: an index of the flows and, per flow, a page that
creates objects and moves them with ``{% flow_status %}``."""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from djgentelella.flows import TransitionNotAllowed, get_flow
from djgentelella.flows.models import FlowInstance, Task
from djgentelella.flows.timers import process_due

from . import forms


class Demo:
    def __init__(self, slug, flow, form, owner, description, features, title,
                 filter=None, board=''):
        self.slug = slug
        self.flow_name = flow
        self.form = form
        #: The field set to the user who creates the object.
        self.owner = owner
        self.description = description
        self.features = features
        #: The menu title: a JSON flow does not exist before createdemo loads it.
        self.title = title
        #: Field values of the objects of this demo, when two demos share a
        #: model; they are set on the objects it creates.
        self.filter = filter or {}
        #: The path of a design page with its kanban board (flow_kanban).
        self.board = board

    @property
    def flow(self):
        return get_flow(self.flow_name)


DEMOS = [
    Demo('purchases', 'demoapp.PurchaseFlow', forms.PurchaseRequestForm, 'requester',
         _('A request under 1000 is approved on submission; a larger one goes to '
           'the purchase committee: every member gets a task, and two approvals '
           'decide it. Ordering asks for the supplier and a quote.'),
         [_('Automatic gateway'), _('Quorum (2 tasks)'), _('Human tasks'),
          _('Reminder on expiry'), _('Form with a file'), _('Hooks on enter')],
         _('Purchase requests')),
    Demo('tickets', 'demoapp.TicketFlow', forms.SupportTicketForm, 'reporter',
         _('A new ticket is triaged into the Support queue at once. A member '
           'claims it or starts it; past its SLA (4 hours high, 2 days normal, '
           '5 days low) it is escalated. Resolved tickets close in bulk.'),
         [_('Automatic triage'), _('Claim / release'), _('SLA by priority'),
          _('Cancel from any state'), _('Bulk close'), _('ModelForm transition')],
         _('Help desk'), board='tickets-board'),
    Demo('documents', 'demoapp.EditorialFlow', forms.EditorialDocumentForm, 'author',
         _('The author sends the text to review once it is long enough; an editor '
           'who is not the author publishes it or asks for changes, with notes '
           'saved on the document.'),
         [_('Reasons on disabled buttons'), _('Changes loop'), _('Hooks on exit'),
          _('Custom permission'), _('SetField with a callable')],
         _('Editorial review')),
    Demo('leaves', 'demoapp.LeaveFlow', forms.LeaveRequestForm, 'employee',
         _('The employee picks who approves. Only that person decides; after two '
           'days without an answer, the request is approved by silence. An '
           'approved leave is added to the demo calendar once committed.'),
         [_('Approver from a field'), _('Tacit approval (deadline)'),
          _('on_commit action'), _('Conditions with reasons')], _('Leave requests')),
    Demo('countries', 'demoapp.CountryApprovalFlow', None, None,
         _('The minimal example of the documentation: submit, approve or reject, '
           'reopen.'),
         [_('Permissions'), _('Notify'), _('SetField')], _('Country approval')),
    Demo('expenses', 'demoapp.ExpenseFlow', forms.ExpenseReportForm, 'requester',
         _('A switch by amount: under 1000 the manager approves; from 1000 the '
           'manager and finance decide in parallel, and both must approve. An '
           'approved expense waits for the payment signal. Open the task inbox '
           'to decide.'),
         [_('Switch'), _('Human tasks'), _('Parallel + join'), _('Wait for a signal'),
          _('Escalation'), _('Variables')], _('Expense approval'),
         filter={'flow_name': 'demoapp.ExpenseFlow'}),
    Demo('expenses-json', 'demoapp.expenses_json', forms.ExpenseReportForm,
         'requester',
         _('The same expense approval, written in JSON '
           '(demoapp/flowdemos/expense_flow.json) and loaded into a '
           'FlowDefinition by createdemo: publishing a new version does not '
           'touch the expenses already under way.'),
         [_('FlowDefinition'), _('JSON'), _('Versions')],
         _('Expense approval (JSON)'),
         filter={'flow_name': 'demoapp.expenses_json'}),
]


def demo_or_404(slug):
    for demo in DEMOS:
        if demo.slug == slug:
            return demo
    raise Http404()


@login_required
def flow_demo_index(request):
    return render(request, 'gentelella/flowdemos/index.html', {'demos': DEMOS})


@login_required
def flow_demo_list(request, slug):
    demo = demo_or_404(slug)
    flow = demo.flow
    form = None
    if demo.form is not None:
        form = demo.form(request.POST if request.method == 'POST' else None,
                         prefix='demo')
        if request.method == 'POST' and form.is_valid():
            obj = form.save(commit=False)
            setattr(obj, demo.owner, request.user)
            for field, value in demo.filter.items():
                setattr(obj, field, value)
            obj.save()
            # Enters the initial state: its automatic transitions run (the
            # ticket triage).
            flow.start(obj, request.user, request=request)
            messages.success(request, _('%(object)s created.') % {'object': obj})
            return HttpResponseRedirect(request.path)
    objects = flow.get_queryset(request.user).filter(**demo.filter).order_by(
        '-pk')[:50]
    return render(request, 'gentelella/flowdemos/list.html', {
        'demo': demo, 'flow': flow, 'form': form, 'objects': objects,
        'can_pay': request.user.has_perm('demoapp.change_expensereport')
        and 'flow_name' in demo.filter})


@require_POST
@user_passes_test(lambda user: user.is_superuser)
def flow_demo_expire(request):
    """Demo only: bring every pending deadline to now and run them, instead of
    waiting for ``process_flow_timers`` on cron."""
    names = [demo.flow_name for demo in DEMOS]
    past = timezone.now() - timedelta(seconds=1)
    instances = FlowInstance.objects.filter(flow__in=names, due_at__isnull=False)
    for instance in instances:  # the timers live in each token
        for token in instance.tokens:
            if token.get('due'):
                token['due'] = past.isoformat()
        instance.due_at = past
        instance.save(update_fields=['tokens', 'due_at'])
    moved = len(instances)
    tasks = Task.objects.filter(instance__flow__in=names, state__in=Task.OPEN,
                                due__isnull=False)
    moved += tasks.update(due=past)
    counts = process_due()
    messages.info(request, _('%(due)d deadlines expired: %(counts)s') % {
        'due': moved, 'counts': ', '.join('%s %d' % item for item in counts.items())
        or '-'})
    return HttpResponseRedirect(reverse('flow_demo_index'))


@require_POST
@login_required
def flow_demo_pay(request, slug, pk):
    """The expense demos: send the ``paid`` signal the payment waits for."""
    demo = demo_or_404(slug)
    flow = demo.flow
    obj = flow.get_queryset(request.user).filter(pk=pk).first()
    if obj is None or not request.user.has_perm('demoapp.change_expensereport'):
        raise Http404()
    try:
        woken = flow.signal(obj, 'paid', {'paid_by': request.user.username},
                            user=request.user)
    except TransitionNotAllowed as error:
        messages.error(request, str(error))
    else:
        if woken:
            messages.success(request, _('%(object)s is paid.') % {'object': obj})
        else:
            messages.warning(request, _('%(object)s is not waiting for a payment.')
                             % {'object': obj})
    return HttpResponseRedirect(reverse('flow_demo_list', args=[slug]))
