from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from demoapp.flowdemos.seed import seed, task_of
from demoapp.flowdemos.views import DEMOS
from demoapp.models import Event, EditorialDocument, ExpenseReport, LeaveRequest, \
    PurchaseRequest, SupportTicket
from djgentelella.flows import get_flow
from djgentelella.flows.models import FlowDefinition, Task


def states(flow_name, model, field):
    flow = get_flow(flow_name)
    return {getattr(obj, field): flow.state(obj) for obj in model.objects.all()}


class FlowDemoSeedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with cls.captureOnCommitCallbacks(execute=True):
            seed()
        cls.ana = get_user_model().objects.get(username='ana')
        cls.beto = get_user_model().objects.get(username='beto')
        cls.carla = get_user_model().objects.get(username='carla')

    def test_every_object_is_where_the_seed_left_it(self):
        self.assertEqual(states('demoapp.PurchaseFlow', PurchaseRequest, 'title'), {
            'Keyboards for the lab': 'approved', 'Rack server': 'committee',
            'Projector': 'ordered', 'Design licenses': 'draft'})
        self.assertEqual(states('demoapp.TicketFlow', SupportTicket, 'subject'), {
            'The printer does not print': 'queued', 'The VPN is down': 'in_progress',
            'A new monitor': 'resolved', 'Reset my password': 'resolved',
            'Mail bounces': 'queued'})
        self.assertEqual(states('demoapp.EditorialFlow', EditorialDocument, 'title'), {
            'A short note': 'draft', 'Annual report': 'review',
            'Style guide': 'changes', 'Welcome page': 'published'})
        self.assertEqual(sorted(states('demoapp.LeaveFlow', LeaveRequest,
                                       'reason').values()),
                         ['approved', 'draft', 'requested'])
        self.assertTrue(Event.objects.filter(title__startswith='Vacaciones').exists())
        self.assertEqual(PurchaseRequest.objects.get(title='Projector').supplier,
                         'ACME')
        for flow_name in ('demoapp.ExpenseFlow', 'demoapp.expenses_json'):
            found = {obj.title: get_flow(flow_name).state(obj)
                     for obj in ExpenseReport.objects.filter(flow_name=flow_name)}
            self.assertEqual(found, {
                'Taxi to the airport': 'draft', 'Lunch with a client': 'manager',
                'Laptop': 'review', 'Train tickets': 'payment'}, flow_name)

    def test_seeding_twice_starts_over(self):
        seed()
        self.assertEqual(PurchaseRequest.objects.count(), 4)
        # The JSON definition is published once, not once per seed.
        self.assertEqual(FlowDefinition.objects.filter(
            name='demoapp.expenses_json').count(), 1)

    def test_the_committee_vote_is_carla_s(self):
        flow = get_flow('demoapp.PurchaseFlow')
        server = PurchaseRequest.objects.get(title='Rack server')
        task_of(server, self.carla).complete(self.carla, 'approve')
        self.assertEqual(flow.state(server), 'approved')

    def test_the_laptop_needs_finance_too(self):
        for flow_name in ('demoapp.ExpenseFlow', 'demoapp.expenses_json'):
            flow = get_flow(flow_name)
            laptop = ExpenseReport.objects.get(title='Laptop', flow_name=flow_name)
            task_of(laptop, self.carla).complete(self.carla, 'approve')
            self.assertEqual(flow.state(laptop), 'payment', flow_name)
            self.client.force_login(self.carla)
            slug = 'expenses' if flow_name == 'demoapp.ExpenseFlow' else \
                'expenses-json'
            self.client.post(reverse('flow_demo_pay', args=[slug, laptop.pk]))
            laptop.refresh_from_db()
            self.assertEqual((flow.state(laptop), laptop.paid), ('closed', True))

    def test_task_inbox(self):
        self.client.force_login(self.beto)
        page = self.client.get(reverse('task_inbox'))
        self.assertContains(page, 'Approve the expense: Lunch with a client', count=2)
        task = Task.objects.inbox(self.beto).filter(title__contains='Lunch').first()
        detail = self.client.get(reverse('task_detail', args=[task.pk]))
        self.assertContains(detail, 'name="outcome" value="approve"')

    def test_pages(self):
        self.client.force_login(self.ana)
        index = self.client.get(reverse('flow_demo_index'))
        self.assertContains(index, '<svg', count=len(DEMOS))
        for demo in DEMOS:
            page = self.client.get(reverse('flow_demo_list', args=[demo.slug]))
            self.assertEqual(page.status_code, 200, demo.slug)
            inbox = self.client.get(reverse('flow_inbox', args=[demo.flow_name]))
            self.assertEqual(inbox.status_code, 200, demo.slug)
        documents = self.client.get(reverse('flow_demo_list', args=['documents']))
        self.assertContains(documents, 'The text needs 50 characters at least')

    def test_creating_a_ticket_triages_it(self):
        self.client.force_login(self.ana)
        url = reverse('flow_demo_list', args=['tickets'])
        self.client.post(url, {'demo-subject': 'No sound', 'demo-priority': 'low',
                               'demo-description': 'The speakers are mute.'})
        ticket = SupportTicket.objects.get(subject='No sound')
        self.assertEqual((ticket.reporter, get_flow('demoapp.TicketFlow').state(
            ticket)), (self.ana, 'queued'))

    def test_expire_the_deadlines(self):
        url = reverse('flow_demo_expire')
        self.client.force_login(self.ana)
        self.client.post(url)  # not a superuser: nothing happens
        flow = get_flow('demoapp.LeaveFlow')
        pending = LeaveRequest.objects.get(reason='Family trip')
        self.assertEqual(flow.state(pending), 'requested')
        self.client.force_login(get_user_model().objects.create_superuser(
            'root', password='x'))
        self.client.post(url)
        self.assertEqual(flow.state(pending), 'approved')
        # The normal ticket's SLA passed too: escalated to high.
        printer = SupportTicket.objects.get(subject='The printer does not print')
        self.assertEqual(printer.priority, 'high')
