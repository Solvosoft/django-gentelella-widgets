"""Users, groups and objects in several states for the flow demos.

Called by ``manage.py createdemo``. Every object is moved through its flow
with the engine itself, so the history, the votes and the assignments are
real. The users are ana (asks for things), beto and carla (committee,
support, editors); their password is ``demo``.
"""

import json
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.utils import timezone

from demoapp.gtflows import EDITORS, FINANCE, PURCHASE_COMMITTEE, SUPPORT
from demoapp.models import EditorialDocument, ExpenseReport, LeaveRequest, \
    PurchaseRequest, SupportTicket
from djgentelella.flows import get_flow, publish_definition
from djgentelella.flows.models import FlowDefinition, Task

MODELS = [PurchaseRequest, SupportTicket, EditorialDocument, LeaveRequest,
          ExpenseReport]
#: The JSON twin of demoapp.ExpenseFlow.
EXPENSE_FLOW_JSON = Path(__file__).with_name('expense_flow.json')
LONG_TEXT = ('A text long enough to be sent to review: the editorial flow asks '
             'for fifty characters at least before an editor sees it.')


def demo_user(name, permissions, groups=()):
    user, created = get_user_model().objects.get_or_create(
        username=name, defaults={'first_name': name.capitalize(),
                                 'email': '%s@example.com' % name})
    if created:
        user.set_password('demo')
        user.save()
    user.user_permissions.add(*permissions)
    user.groups.add(*groups)
    return user


def create_users():
    groups = [Group.objects.get_or_create(name=name)[0]
              for name in (PURCHASE_COMMITTEE, SUPPORT, EDITORS)]
    finance = Group.objects.get_or_create(name=FINANCE)[0]
    codenames = ['%s_%s' % (action, model._meta.model_name)
                 for action in ('view', 'add', 'change') for model in MODELS]
    permissions = list(Permission.objects.filter(
        content_type__app_label='demoapp', codename__in=codenames))
    reviewer = permissions + [Permission.objects.get(
        codename='review_editorialdocument')]
    return (demo_user('ana', permissions),
            demo_user('beto', reviewer, groups),
            demo_user('carla', reviewer, groups + [finance]))


def task_of(obj, user):
    """The open task of ``user`` on ``obj``."""
    return Task.objects.inbox(user).get(object_id=str(obj.pk),
                                        content_type__model=obj._meta.model_name)


def create_purchases(ana, beto, carla):
    flow = get_flow('demoapp.PurchaseFlow')
    new = PurchaseRequest.objects.create
    small = new(title='Keyboards for the lab', amount=250, requester=ana,
                justification='Three keyboards are broken.')
    flow.run(small, 'submit', ana)  # under 1000: approved by the gateway
    server = new(title='Rack server', amount=8000, requester=ana,
                 justification='The old one is out of warranty.')
    flow.run(server, 'submit', ana)  # to the committee: one task each
    task_of(server, beto).complete(beto, 'approve')  # 1 of 2: carla's is missing
    projector = new(title='Projector', amount=1800, requester=ana)
    flow.run(projector, 'submit', ana)
    task_of(projector, beto).complete(beto, 'approve')
    task_of(projector, carla).complete(carla, 'approve')
    flow.run(projector, 'order', ana, data={'supplier': 'ACME',
                                            'order_number': 'PO-1001'})
    new(title='Design licenses', amount=3000, requester=ana)  # a draft


def create_tickets(ana, beto, carla):
    flow = get_flow('demoapp.TicketFlow')

    def ticket(subject, priority, description=''):
        obj = SupportTicket.objects.create(subject=subject, priority=priority,
                                           reporter=ana,
                                           description=description or subject)
        flow.evaluate(obj, ana)  # the automatic triage into the queue
        return obj

    ticket('The printer does not print', 'normal')
    vpn = ticket('The VPN is down', 'high')
    flow.claim(vpn, beto)
    flow.run(vpn, 'start', beto)
    for subject, who in (('A new monitor', carla), ('Reset my password', beto)):
        obj = ticket(subject, 'low')
        flow.run(obj, 'start', who)
        obj.resolution = 'Done.'
        obj.save()
        flow.run(obj, 'resolve', who)  # both resolved: close them in bulk
    late = ticket('Mail bounces', 'high')
    instance = flow.get_instance(late)
    instance.due_at = timezone.now() - timedelta(hours=1)  # past its SLA
    instance.save()


def create_documents(ana, beto, carla):
    flow = get_flow('demoapp.EditorialFlow')
    new = EditorialDocument.objects.create
    new(title='A short note', body='Too short to review.', author=ana)
    report = new(title='Annual report', body=LONG_TEXT, author=ana)
    flow.run(report, 'send', ana)
    guide = new(title='Style guide', body=LONG_TEXT, author=ana)
    flow.run(guide, 'send', ana)
    guide.reviewer_notes = 'Add examples to every rule.'
    guide.save()
    flow.run(guide, 'request_changes', beto)
    welcome = new(title='Welcome page', body=LONG_TEXT, author=ana)
    flow.run(welcome, 'send', ana)
    flow.run(welcome, 'publish', carla)


def create_leaves(ana, beto, carla):
    flow = get_flow('demoapp.LeaveFlow')
    today = timezone.localdate()
    new = LeaveRequest.objects.create
    pending = new(employee=ana, approver=beto, start=today + timedelta(days=10),
                  end=today + timedelta(days=14), reason='Family trip')
    flow.run(pending, 'request', ana)
    approved = new(employee=ana, approver=carla, start=today + timedelta(days=30),
                   end=today + timedelta(days=35), reason='Holidays')
    flow.run(approved, 'request', ana)
    flow.run(approved, 'approve', carla)  # and to the calendar, on commit
    new(employee=beto, approver=carla, start=today + timedelta(days=60),
        end=today + timedelta(days=61))  # a draft


def load_expense_definition():
    """Publish ``expense_flow.json`` unless that document is already the
    active version."""
    with open(EXPENSE_FLOW_JSON, encoding='utf-8') as handle:
        document = json.load(handle)
    current = FlowDefinition.objects.filter(name=document['name'], site=None,
                                            is_active=True).first()
    if current is not None and {key: value for key, value in current.document.items()
                                if key != 'version'} == document:
        return current
    return publish_definition(document)


def create_expenses(ana, beto, carla):
    load_expense_definition()
    for flow_name in ('demoapp.ExpenseFlow', 'demoapp.expenses_json'):
        flow = get_flow(flow_name)

        def expense(title, amount):
            obj = ExpenseReport.objects.create(title=title, amount=amount,
                                               requester=ana, manager=beto,
                                               flow_name=flow_name)
            flow.start(obj, ana)
            return obj

        expense('Taxi to the airport', 40)  # a draft
        lunch = expense('Lunch with a client', 120)
        flow.run(lunch, 'submit', ana)  # beto's task
        laptop = expense('Laptop', 1500)
        flow.run(laptop, 'submit', ana)  # beto and finance in parallel
        task_of(laptop, beto).complete(beto, 'approve')  # finance is missing
        train = expense('Train tickets', 300)
        flow.run(train, 'submit', ana)
        task_of(train, beto).complete(beto, 'approve')  # waiting for the payment


def seed():
    users = create_users()
    for model in MODELS:
        model.objects.all().delete()  # their flow state goes with them
    create_purchases(*users)
    create_tickets(*users)
    create_documents(*users)
    create_leaves(*users)
    create_expenses(*users)
