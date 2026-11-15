"""The flow demos: one flow per kind of process the engine builds.

Each one shows a different part of djgentelella.flows; /flowdemos/ lists them
with their diagrams. ``manage.py createdemo`` makes the groups, the users
(ana, beto, carla; password ``demo``) and objects in every state.

* CountryApprovalFlow -- the minimal example of docs/source/flows.rst.
* PurchaseFlow -- automatic gateway by amount, committee quorum, reminder.
* TicketFlow -- automatic triage, group queue to claim, SLA by priority,
  cancel from any state, bulk close.
* EditorialFlow -- a ModelForm in a transition, reasons on disabled buttons,
  hooks, a loop back for changes.
* LeaveFlow -- the approver is a field of the object, tacit approval when
  nobody answers in time, an on_commit action (the calendar).
* ExpenseFlow -- a switch by amount, the manager's human task and, for a
  large amount, the manager and finance in parallel; then a wait for the
  payment signal. ``flowdemos/expense_flow.json`` is the same flow in JSON,
  loaded into a FlowDefinition as ``demoapp.expenses_json``.

Conditions get the run's context: ``context.obj``, ``context.user`` (None
for the system) and ``context.variables``.
"""
from datetime import timedelta

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from djgentelella.flows import (
    ANY_STATE,
    ActionActivity,
    Assign,
    CallFunction,
    Deadline,
    Flow,
    HumanTask,
    Join,
    Notify,
    Parallel,
    SetField,
    SetVariable,
    Switch,
    Transition,
    TransitionBlocked,
    Wait,
    register_condition,
    register_flow,
)

from .flowdemos.forms import PurchaseOrderForm, ResolutionForm, ReviewNotesForm
from .models import (
    Country,
    EditorialDocument,
    ExpenseReport,
    LeaveRequest,
    PurchaseRequest,
    SupportTicket,
)

PURCHASE_COMMITTEE = 'Purchase committee'
SUPPORT = 'Support'
EDITORS = 'Editors'
FINANCE = 'Finance'
#: Below it a purchase is approved without the committee.
SMALL_PURCHASE = 1000
#: From it on, an expense needs finance as well as the manager.
LARGE_EXPENSE = 1000


@register_flow
class CountryApprovalFlow(Flow):
    title = _('Country approval')
    model = Country
    states = [('draft', _('Draft')), ('review', _('In review')),
              ('approved', _('Approved')), ('rejected', _('Rejected'))]
    initial = 'draft'
    transitions = [
        Transition('submit', 'draft', 'review', label=_('Submit for review'),
                   perms=['demoapp.change_country'], icon='fa fa-paper-plane'),
        Transition('approve', 'review', 'approved', label=_('Approve'),
                   perms=['demoapp.view_country'], css_class='btn-success',
                   actions=[Notify('{{ object }} was approved.', to='actor',
                                   message_type='success')]),
        Transition('reject', 'review', 'rejected', label=_('Reject'),
                   perms=['demoapp.view_country'], css_class='btn-danger'),
        Transition('reopen', ['approved', 'rejected'], 'draft', label=_('Reopen'),
                   perms=['demoapp.change_country'], css_class='btn-secondary',
                   actions=[SetField('code', '')]),
    ]


# -- purchases -----------------------------------------------------------------
def has_an_amount(context):
    if context.obj.amount <= 0:
        raise TransitionBlocked(_('Say how much it costs first.'))
    return True


def is_small(context):
    return context.obj.amount < SMALL_PURCHASE


@register_flow
class PurchaseFlow(Flow):
    title = _('Purchase requests')
    model = PurchaseRequest
    states = [
        ('draft', _('Draft')), ('check', _('Checking the amount')),
        # Every member of the committee gets a task; two approvals decide it,
        # and so does a veto once two approvals are out of reach. Past five
        # days the members still deciding get a reminder.
        HumanTask('committee', _('In committee'),
                  title=_('Approve the purchase: {{ object }}'),
                  groups=[PURCHASE_COMMITTEE], each=True, min=2,
                  outcomes={'approve': 'approved', 'reject': 'rejected'},
                  due=timedelta(days=5),
                  on_expire={'notify': '{{ object }} has waited five days for the '
                                       'committee.'},
                  on_enter=[Notify('{{ object }} went to the purchase committee.',
                                   to='field:requester')]),
        ('approved', _('Approved')), ('rejected', _('Rejected')),
        ('ordered', _('Ordered'))]
    initial = 'draft'
    on_enter = {
        'approved': [Notify('{{ object }} is approved.', to='field:requester',
                            message_type='success')],
        'rejected': [Notify('{{ object }} was rejected.', to='field:requester',
                            message_type='danger')],
    }
    transitions = [
        Transition('submit', 'draft', 'check', label=_('Submit'),
                   perms=['demoapp.change_purchaserequest'], icon='fa fa-paper-plane',
                   condition=has_an_amount),
        # The gateway: the first automatic transition whose condition holds.
        Transition('small', 'check', 'approved', label=_('Small amount'), auto=True,
                   condition=is_small),
        Transition('large', 'check', 'committee', label=_('Large amount'),
                   auto=True),
        Transition('order', 'approved', 'ordered', label=_('Place the order'),
                   perms=['demoapp.change_purchaserequest'], form=PurchaseOrderForm,
                   icon='fa fa-truck',
                   actions=[SetField('supplier',
                                     lambda context: context.data['supplier'])]),
    ]


# -- support tickets -------------------------------------------------------------
SLA = {'high': timedelta(hours=4), 'normal': timedelta(days=2),
       'low': timedelta(days=5)}


def sla(context):
    return timezone.now() + SLA[context.obj.priority]


@register_flow
class TicketFlow(Flow):
    title = _('Help desk')
    model = SupportTicket
    states = [('new', _('New')), ('queued', _('In the queue')),
              ('in_progress', _('In progress')), ('waiting', _('Waiting for the user')),
              ('resolved', _('Resolved')), ('closed', _('Closed')),
              ('cancelled', _('Cancelled'))]
    initial = 'new'
    final_states = ['closed', 'cancelled']
    on_enter = {'queued': [Assign(group=SUPPORT)]}
    deadlines = {'queued': Deadline(sla, transition='escalate')}
    transitions = [
        # Run by flow.evaluate() right after the ticket is created.
        Transition('triage', 'new', 'queued', label=_('Triage'), auto=True),
        Transition('escalate', 'queued', 'queued', label=_('Escalate'),
                   perms=['demoapp.delete_supportticket'], keep_assignment=True,
                   actions=[SetField('priority', 'high'),
                            Notify('{{ object }} is past its SLA.', to='assigned',
                                   message_type='warning')]),
        Transition('start', 'queued', 'in_progress', label=_('Start'),
                   perms=['demoapp.change_supportticket'], icon='fa fa-play',
                   actions=[Assign(user='actor')]),
        Transition('wait', 'in_progress', 'waiting', label=_('Ask the user'),
                   perms=['demoapp.change_supportticket'], keep_assignment=True,
                   css_class='btn-secondary'),
        Transition('resume', 'waiting', 'in_progress', label=_('Resume'),
                   perms=['demoapp.change_supportticket'], keep_assignment=True),
        Transition('resolve', 'in_progress', 'resolved', label=_('Resolve'),
                   perms=['demoapp.change_supportticket'], form=ResolutionForm,
                   css_class='btn-success', keep_assignment=True,
                   actions=[Notify('{{ object }}: {{ object.resolution }}',
                                   to='field:reporter', message_type='success')]),
        Transition('reopen', 'resolved', 'queued', label=_('Reopen'),
                   css_class='btn-secondary',
                   condition=lambda context: context.user is None
                   or context.user == context.obj.reporter
                   or context.user.is_superuser),
        Transition('close', 'resolved', 'closed', label=_('Close'),
                   perms=['demoapp.change_supportticket']),
        Transition('cancel', ANY_STATE, 'cancelled', label=_('Cancel'),
                   perms=['demoapp.delete_supportticket'], css_class='btn-danger'),
    ]


# -- editorial review ------------------------------------------------------------
MIN_LENGTH = 50


def long_enough(context):
    body = context.obj.body
    if len(body) < MIN_LENGTH:
        raise TransitionBlocked(
            _('The text needs %(min)d characters at least; it has %(has)d.')
            % {'min': MIN_LENGTH, 'has': len(body)})
    return True


def not_the_author(context):
    if context.user is not None and context.user == context.obj.author:
        raise TransitionBlocked(_('Nobody reviews their own text.'))
    return True


def by_the_author(context):
    user = context.user
    return user is None or user == context.obj.author or user.is_superuser


@register_flow
class EditorialFlow(Flow):
    title = _('Editorial review')
    model = EditorialDocument
    states = [('draft', _('Draft')), ('review', _('In review')),
              ('changes', _('Changes requested')), ('published', _('Published')),
              ('archived', _('Archived'))]
    initial = 'draft'
    on_enter = {'review': [Assign(group=EDITORS)]}
    on_exit = {'review': [Notify('{{ object }}: {{ transition.label }}.',
                                 to='field:author')]}
    transitions = [
        Transition('send', ['draft', 'changes'], 'review', label=_('Send to review'),
                   perms=['demoapp.change_editorialdocument'],
                   condition=lambda context: by_the_author(context)
                   and long_enough(context)),
        Transition('request_changes', 'review', 'changes', label=_('Request changes'),
                   perms=['demoapp.review_editorialdocument'], form=ReviewNotesForm,
                   css_class='btn-warning', condition=not_the_author),
        Transition('publish', 'review', 'published', label=_('Publish'),
                   perms=['demoapp.review_editorialdocument'], css_class='btn-success',
                   condition=not_the_author,
                   actions=[SetField('published_at', lambda context: timezone.now())]),
        Transition('archive', 'published', 'archived', label=_('Archive'),
                   perms=['demoapp.review_editorialdocument'],
                   css_class='btn-secondary'),
    ]


# -- leave requests ---------------------------------------------------------------
def is_the_approver(context):
    user, leave = context.user, context.obj
    if user is None or user.is_superuser or user == leave.approver:
        return True
    raise TransitionBlocked(_('Only %(approver)s decides it.') % {
        'approver': leave.approver})


def is_the_employee(context):
    user, leave = context.user, context.obj
    if user is None or user.is_superuser or user == leave.employee:
        return True
    raise TransitionBlocked(_('Only %(employee)s can do it.') % {
        'employee': leave.employee})


@register_flow
class LeaveFlow(Flow):
    title = _('Leave requests')
    model = LeaveRequest
    states = [('draft', _('Draft')), ('requested', _('Requested')),
              ('approved', _('Approved')), ('rejected', _('Rejected')),
              ('cancelled', _('Cancelled'))]
    initial = 'draft'
    final_states = ['rejected', 'cancelled']
    on_enter = {
        'approved': [
            CallFunction('demoapp.flowdemos.actions.add_to_calendar', on_commit=True),
            Notify('Your leave {{ object.start }} - {{ object.end }} is approved.',
                   to='field:employee', message_type='success'),
        ],
    }
    deadlines = {
        # Silence means yes: two days without an answer approve it.
        'requested': Deadline(timedelta(days=2), transition='tacit_approval'),
    }
    transitions = [
        Transition('request', 'draft', 'requested', label=_('Request'),
                   perms=['demoapp.change_leaverequest'], condition=is_the_employee,
                   actions=[Assign(user='field:approver'),
                            Notify('{{ object.employee }} asks for leave.',
                                   to='field:approver')]),
        Transition('approve', 'requested', 'approved', label=_('Approve'),
                   perms=['demoapp.view_leaverequest'], css_class='btn-success',
                   condition=is_the_approver),
        Transition('reject', 'requested', 'rejected', label=_('Reject'),
                   perms=['demoapp.view_leaverequest'], css_class='btn-danger',
                   condition=is_the_approver),
        Transition('tacit_approval', 'requested', 'approved',
                   label=_('Approve by silence'),
                   perms=['demoapp.delete_leaverequest'], css_class='btn-secondary'),
        Transition('cancel', ['draft', 'requested', 'approved'], 'cancelled',
                   label=_('Cancel'), perms=['demoapp.change_leaverequest'],
                   css_class='btn-danger', condition=is_the_employee),
    ]


# -- expenses ---------------------------------------------------------------------
# Registered by name: the JSON version of the flow names them.
@register_condition('demoapp.expense_is_large')
def expense_is_large(context):
    return context.obj.amount >= LARGE_EXPENSE


@register_condition('demoapp.expense_both_approved')
def expense_both_approved(context):
    return (context.variables.get('manager_review_outcome') == 'approve'
            and context.variables.get('finance_review_outcome') == 'approve')


@register_condition('demoapp.expense_by_requester')
def expense_by_requester(context):
    user = context.user
    if user is None or user.is_superuser or user == context.obj.requester:
        return True
    raise TransitionBlocked(_('Only %(requester)s can submit it.') % {
        'requester': context.obj.requester})


@register_flow
class ExpenseFlow(Flow):
    """An expense report: a small one needs its manager, a large one its
    manager *and* finance, at the same time. Once approved it waits for the
    payment: ``flow.signal(expense, 'paid')``.

    ``flowdemos/expense_flow.json`` declares exactly this flow in JSON.
    """

    title = _('Expense approval')
    model = ExpenseReport
    states = [
        ('draft', _('Draft')),
        Switch('route', _('Small or large?'),
               cases=[('demoapp.expense_is_large', 'review')], default='manager'),
        HumanTask('manager', _('Manager approval'),
                  title=_('Approve the expense: {{ object }}'),
                  owners=['field:manager'], priority=3, due=timedelta(days=3),
                  on_expire={'escalate': {'groups': [FINANCE], 'priority': 1},
                             'notify': '{{ object }} is waiting for approval.'},
                  outcomes={'approve': 'approved', 'reject': 'rejected'}),
        Parallel('review', _('Manager and finance'),
                 branches=['manager_review', 'finance_review']),
        HumanTask('manager_review', _('Manager approval'),
                  title=_('Approve the expense: {{ object }}'),
                  owners=['field:manager'], priority=2,
                  outcomes={'approve': 'reviewed', 'reject': 'reviewed'}),
        HumanTask('finance_review', _('Finance approval'),
                  title=_('Finance: approve {{ object }}'), groups=[FINANCE],
                  priority=2, due=timedelta(days=5),
                  on_expire={'outcome': 'reject'},
                  outcomes={'approve': 'reviewed', 'reject': 'reviewed'}),
        Join('reviewed', _('Both answered'), wait_for='all', next='decide'),
        Switch('decide', _('Both approved?'),
               cases=[('demoapp.expense_both_approved', 'approved')],
               default='rejected'),
        ActionActivity('approved', _('Approved'), next='payment', actions=[
            SetVariable('approved_amount', lambda context: str(context.obj.amount)),
            Notify('{{ object }} is approved.', to='field:requester',
                   message_type='success')]),
        Wait('payment', _('Waiting for the payment'), signal='paid', next='paid'),
        ActionActivity('paid', _('Paid'), next='closed',
                       actions=[SetField('paid', True)]),
        ('closed', _('Closed')),
        ('rejected', _('Rejected')),
    ]
    initial = 'draft'
    final_states = ['closed', 'rejected']
    on_enter = {'rejected': [Notify('{{ object }} was rejected.',
                                    to='field:requester', message_type='danger')]}
    transitions = [
        Transition('submit', 'draft', 'route', label=_('Submit'),
                   perms=['demoapp.change_expensereport'], icon='fa fa-paper-plane',
                   condition='demoapp.expense_by_requester'),
    ]
