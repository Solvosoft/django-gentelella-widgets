"""Flows v2: activities (switch, wait, parallel/join, subflow, human task,
action), variables, instance control, versions, JSON definitions, the action
registry, tasks and their inbox, timers and the runtime diagram."""

import json
import threading
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest import skipUnless

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from demoapp.models import Country, ExpenseReport
from djgentelella.flows import (
    ActionActivity,
    CallFunction,
    Flow,
    HumanTask,
    Join,
    Parallel,
    SetVariable,
    Subflow,
    Switch,
    TaskNotAllowed,
    Transition,
    TransitionNotAllowed,
    Wait,
    action_from_json,
    build_flow,
    create_task,
    flow_state_changed,
    get_action,
    get_flow,
    publish_definition,
    register_condition,
    register_flow,
    task_completed,
    task_created,
)
from djgentelella.flows.actions import ActionContext, Notify, SetField
from djgentelella.flows.diagram import render_svg
from djgentelella.flows.models import FlowDefinition, FlowInstance, Task
from djgentelella.flows.timers import process_due
from djgentelella.models import Notification

EXPENSE_JSON = (Path(__file__).resolve().parents[2] / 'demo' / 'demoapp'
                / 'flowdemos' / 'expense_flow.json')


def make_user(name, *codenames, groups=()):
    user = get_user_model().objects.create_user(name, password='x')
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
    for group in groups:
        user.groups.add(group)
    return user


def root():
    found = get_user_model().objects.filter(username='root').first()
    return found or get_user_model().objects.create_superuser('root', password='x')


def later(**delta):
    return timezone.now() + timedelta(**delta)


# -- flows under test -------------------------------------------------------------
@register_condition('tests.v2.is_big')
def is_big(context):
    return context.variables.get('amount', 0) >= 100


FLAKY = {'fail': True}


def flaky(context):
    if FLAKY['fail']:
        raise RuntimeError('the service is down')
    context.variables['called'] = True


class AmountForm(forms.Form):
    amount = forms.IntegerField()
    note = forms.CharField(required=False)


@register_flow
class ActivityFlow(Flow):
    name = 'tests.v2.activities'
    model = Country
    variables = {'amount': 0}
    states = [
        ('start', 'Start'),
        Switch('route', cases=[('tests.v2.is_big', 'big')], default='small'),
        ('small', 'Small'), ('big', 'Big'),
        Wait('cooling', after=timedelta(hours=1), next='cooled'),
        Wait('until_date', until='deadline', next='cooled'),
        Wait('payment', signal='paid', after=timedelta(days=3), next='paid'),
        ('cooled', 'Cooled'), ('paid', 'Paid'),
        ActionActivity('call', actions=[CallFunction(flaky),
                                        SetVariable('after_call', 'yes')],
                       next='called'),
        ('called', 'Called'),
    ]
    initial = 'start'
    transitions = [
        Transition('route', 'start', 'route', form=AmountForm, variables=['amount']),
        Transition('cool', 'start', 'cooling'),
        Transition('until', 'start', 'until_date'),
        Transition('pay', 'start', 'payment'),
        Transition('call', 'start', 'call'),
        Transition('big_only', 'start', 'big',
                   condition=lambda context: context.variables['amount'] > 10),
        Transition('restart', ['small', 'big', 'cooled', 'paid', 'called'], 'start'),
    ]


@register_flow
class ParallelFlow(Flow):
    name = 'tests.v2.parallel'
    model = Country
    states = [('draft', 'Draft'),
              Parallel('split', branches=['legal', 'tech', 'money']),
              ('legal', 'Legal'), ('tech', 'Tech'), ('money', 'Money'),
              Join('all_done', wait_for='all', next='done'),
              ('done', 'Done')]
    initial = 'draft'
    transitions = [Transition('start', 'draft', 'split'),
                   Transition('ok_legal', 'legal', 'all_done'),
                   Transition('ok_tech', 'tech', 'all_done'),
                   Transition('ok_money', 'money', 'all_done')]


@register_flow
class FirstTwoFlow(Flow):
    name = 'tests.v2.first_two'
    model = Country
    states = [('draft', 'Draft'),
              Parallel('split', branches=['a', 'b', 'c']),
              ('a', 'A'), ('b', 'B'),
              HumanTask('c', groups=['Nobody group'],
                        outcomes={'approve': 'joined', 'reject': 'joined'}),
              Join('joined', wait_for=2, next='done'),
              ('done', 'Done')]
    initial = 'draft'
    transitions = [Transition('start', 'draft', 'split'),
                   Transition('a_ok', 'a', 'joined'),
                   Transition('b_ok', 'b', 'joined')]


@register_flow
class ChildFlow(Flow):
    name = 'tests.v2.child'
    model = Country
    states = [('todo', 'To do'), ('ok', 'OK'), ('ko', 'KO')]
    initial = 'todo'
    transitions = [Transition('accept', 'todo', 'ok',
                              actions=[SetVariable('answer', 42)]),
                   Transition('refuse', 'todo', 'ko')]


@register_flow
class AutoChildFlow(Flow):
    name = 'tests.v2.auto_child'
    model = Country
    states = [('a', 'A'), ('b', 'B')]
    initial = 'a'
    transitions = [Transition('go', 'a', 'b', auto=True)]


@register_flow
class ParentFlow(Flow):
    name = 'tests.v2.parent'
    model = Country
    states = [('draft', 'Draft'),
              Subflow('sub', flow='tests.v2.child', variables={'from_parent': 1},
                      outcomes={'ko': 'refused'}, next='accepted'),
              Subflow('quick', flow='tests.v2.auto_child', next='accepted'),
              ('accepted', 'Accepted'), ('refused', 'Refused')]
    initial = 'draft'
    transitions = [Transition('start', 'draft', 'sub'),
                   Transition('quick', 'draft', 'quick')]


@register_flow
class TaskFlow(Flow):
    name = 'tests.v2.tasks'
    model = Country
    states = [('draft', 'Draft'),
              HumanTask('approval', title='Approve {{ object }}',
                        owners=['user:ana'], groups=['Checkers'], priority=2,
                        due=timedelta(days=1),
                        outcomes={'approve': 'approved', 'reject': 'rejected',
                                  'expired': 'late'}),
              HumanTask('decide', title='Decide {{ object }}', groups=['Checkers'],
                        due=timedelta(days=1), on_expire={'outcome': 'reject'},
                        outcomes={'approve': 'approved', 'reject': 'rejected'}),
              ('approved', 'Approved'), ('rejected', 'Rejected'), ('late', 'Late')]
    initial = 'draft'
    transitions = [Transition('submit', 'draft', 'approval'),
                   Transition('submit_decide', 'draft', 'decide'),
                   Transition('withdraw', 'approval', 'rejected')]


class Version1(Flow):
    name = 'tests.v2.versioned'
    version = 1
    model = Country
    states = [('a', 'A'), ('b', 'B')]
    initial = 'a'
    transitions = [Transition('go', 'a', 'b')]


class Version2(Flow):
    name = 'tests.v2.versioned'
    version = 2
    model = Country
    states = [('a', 'A'), ('c', 'C')]
    initial = 'a'
    transitions = [Transition('go', 'a', 'c')]


register_flow(Version1)


# -- activities -------------------------------------------------------------------
class ActivityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.flow = get_flow('tests.v2.activities')
        cls.root = root()

    def setUp(self):
        FLAKY['fail'] = True
        self.country = Country.objects.create(name='Chile')

    def route(self, amount):
        form = AmountForm({'amount': amount, 'note': 'x'})
        self.assertTrue(form.is_valid())
        return self.flow.run(self.country, 'route', self.root, form=form)

    def test_switch_picks_by_condition(self):
        instance = self.route(150)
        self.assertEqual((instance.state, instance.variables['amount']), ('big', 150))
        self.assertNotIn('note', instance.variables)  # only the fields named
        self.flow.run(self.country, 'restart', self.root)
        self.assertEqual(self.route(5).state, 'small')
        kinds = list(self.flow.history(self.country).values_list('kind', 'target'))
        self.assertIn(('activity', 'small'), kinds)

    def test_switch_without_a_match_is_an_error(self):
        class NoDefault(Flow):
            name = 'tests.v2.no_default'
            model = Country
            states = [('a', 'A'), Switch('s', cases=[(lambda c: False, 'b')]),
                      ('b', 'B')]
            initial = 'a'
            transitions = [Transition('go', 'a', 's')]
        flow = NoDefault()
        instance = flow.run(self.country, 'go', self.root)
        self.assertEqual(instance.status, FlowInstance.ERROR)
        self.assertIn('no case holds', instance.error)

    def test_wait_by_delay(self):
        instance = self.flow.run(self.country, 'cool', self.root)
        self.assertEqual(instance.state, 'cooling')
        self.assertAlmostEqual(instance.due_at, later(hours=1),
                               delta=timedelta(minutes=1))
        self.assertEqual(process_due(later(minutes=30)), {})
        self.assertEqual(process_due(later(hours=2)), {'moved': 1})
        self.assertEqual(self.flow.state(self.country), 'cooled')
        self.assertEqual(self.flow.history(self.country).first().kind, 'timeout')

    def test_wait_until_a_date_in_the_variables(self):
        self.flow.update_variables(self.country, {'deadline': later(days=2)})
        instance = self.flow.run(self.country, 'until', self.root)
        self.assertAlmostEqual(instance.due_at, later(days=2),
                               delta=timedelta(minutes=1))
        self.assertEqual(process_due(later(days=1)), {})
        process_due(later(days=3))
        self.assertEqual(self.flow.state(self.country), 'cooled')

    def test_wait_by_signal(self):
        self.flow.run(self.country, 'pay', self.root)
        self.assertEqual(self.flow.signal(self.country, 'other'), 0)
        self.assertEqual(self.flow.state(self.country), 'payment')
        self.assertEqual(self.flow.signal(self.country, 'paid', {'ref': 'X1'}), 1)
        instance = self.flow.get_instance(self.country)
        self.assertEqual((instance.state, instance.variables['ref']), ('paid', 'X1'))
        self.assertIsNone(instance.due_at)  # the timeout is gone with it
        self.assertEqual(self.flow.history(self.country).first().kind, 'signal')

    def test_signal_or_timeout_whichever_first(self):
        self.flow.run(self.country, 'pay', self.root)
        process_due(later(days=4))
        self.assertEqual(self.flow.state(self.country), 'paid')
        self.assertEqual(self.flow.signal(self.country, 'paid'), 0)

    def test_action_activity_and_variables(self):
        FLAKY['fail'] = False
        instance = self.flow.run(self.country, 'call', self.root)
        self.assertEqual(instance.state, 'called')
        self.assertEqual(instance.variables['called'], True)
        self.assertEqual(instance.variables['after_call'], 'yes')

    def test_conditions_read_variables(self):
        self.assertFalse(self.flow.can_run(self.flow.get_transition('big_only'),
                                           self.country, self.root))
        self.flow.update_variables(self.country, {'amount': 11}, self.root)
        self.assertTrue(self.flow.can_run(self.flow.get_transition('big_only'),
                                          self.country, self.root))
        self.assertEqual(self.flow.history(self.country).first().kind, 'variables')


class ParallelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root = root()

    def test_join_waits_for_all(self):
        flow = get_flow('tests.v2.parallel')
        country = Country.objects.create(name='Peru')
        instance = flow.run(country, 'start', self.root)
        self.assertEqual(instance.state, 'split')
        self.assertEqual(sorted(flow.active_states(instance)),
                         ['legal', 'money', 'tech'])
        buttons = [button.name for button in flow.transition_buttons(country,
                                                                     self.root)]
        self.assertEqual(buttons, ['ok_legal', 'ok_tech', 'ok_money'])
        flow.run(country, 'ok_legal', self.root)
        flow.run(country, 'ok_money', self.root)
        self.assertEqual(flow.state(country), 'split')
        with self.assertRaises(TransitionNotAllowed):
            flow.run(country, 'ok_legal', self.root)
        instance = flow.run(country, 'ok_tech', self.root)
        self.assertEqual((instance.state, len(instance.tokens)), ('done', 1))
        self.assertEqual(instance.status, FlowInstance.COMPLETED)

    def test_join_of_the_first_n_cancels_the_rest(self):
        Group.objects.create(name='Nobody group').user_set.add(self.root)
        flow = get_flow('tests.v2.first_two')
        country = Country.objects.create(name='Peru')
        flow.run(country, 'start', self.root)
        self.assertEqual(flow.tasks(country).open().count(), 1)
        flow.run(country, 'a_ok', self.root)
        instance = flow.run(country, 'b_ok', self.root)
        self.assertEqual(instance.state, 'done')
        self.assertEqual(flow.tasks(country).get().state, Task.CANCELLED)


class SubflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root = root()
        cls.parent = get_flow('tests.v2.parent')
        cls.child = get_flow('tests.v2.child')

    def test_waits_for_the_child(self):
        country = Country.objects.create(name='Peru')
        instance = self.parent.run(country, 'start', self.root)
        self.assertEqual(instance.state, 'sub')
        child = self.child.get_instance(country, create=False)
        self.assertEqual((child.parent, child.variables),
                         (instance, {'from_parent': 1}))
        self.child.run(country, 'accept', self.root)
        instance.refresh_from_db()
        self.assertEqual(instance.state, 'accepted')
        self.assertEqual(instance.variables['sub']['answer'], 42)

    def test_the_child_s_end_picks_the_outcome(self):
        country = Country.objects.create(name='Peru')
        self.parent.run(country, 'start', self.root)
        self.child.run(country, 'refuse', self.root)
        self.assertEqual(self.parent.state(country), 'refused')

    def test_a_child_that_ends_at_once(self):
        country = Country.objects.create(name='Peru')
        self.assertEqual(self.parent.run(country, 'quick', self.root).state,
                         'accepted')


# -- control ------------------------------------------------------------------------
# English labels are asserted: the demo runs in Spanish once its .mo, which is
# not versioned, is compiled, and a local run would disagree with CI.
@override_settings(LANGUAGE_CODE='en')
class ControlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.flow = get_flow('tests.v2.activities')
        cls.root = root()

    def setUp(self):
        FLAKY['fail'] = True
        self.country = Country.objects.create(name='Chile')

    def test_a_failing_action_leaves_an_error_and_retry_completes_it(self):
        instance = self.flow.run(self.country, 'call', self.root)
        self.assertEqual((instance.state, instance.status), ('call', 'error'))
        self.assertIn('the service is down', instance.error)
        self.assertNotIn('after_call', instance.variables)  # undone with it
        self.assertEqual(self.flow.history(self.country).first().kind, 'error')
        with self.assertRaises(TransitionNotAllowed):
            self.flow.resume(self.country, self.root)
        FLAKY['fail'] = False
        instance = self.flow.retry(self.country, self.root)
        self.assertEqual((instance.state, instance.status, instance.error),
                         ('called', 'running', ''))
        self.assertIn('retry', list(self.flow.history(self.country).values_list(
            'kind', flat=True)))
        with self.assertRaises(TransitionNotAllowed):
            self.flow.retry(self.country, self.root)

    def test_suspend_and_resume(self):
        self.flow.run(self.country, 'pay', self.root)
        self.flow.suspend(self.country, self.root, comment='audit')
        with self.assertRaisesMessage(TransitionNotAllowed, 'suspended'):
            self.flow.signal(self.country, 'paid')
        self.assertEqual(process_due(later(days=10)), {})
        self.assertEqual(self.flow.transition_buttons(self.country, self.root), [])
        instance = self.flow.resume(self.country, self.root)
        self.assertEqual(instance.status, 'running')
        self.flow.signal(self.country, 'paid')
        self.assertEqual(self.flow.state(self.country), 'paid')
        kinds = list(self.flow.history(self.country).values_list('kind', flat=True))
        self.assertEqual(kinds[1:3], ['resume', 'suspend'])

    def test_terminate_cancels_the_tasks(self):
        Group.objects.get_or_create(name='Checkers')
        flow = get_flow('tests.v2.tasks')
        flow.run(self.country, 'submit', self.root)
        instance = flow.terminate(self.country, self.root)
        self.assertEqual((instance.status, instance.tokens), ('terminated', []))
        self.assertEqual(flow.tasks(self.country).get().state, Task.CANCELLED)
        with self.assertRaises(TransitionNotAllowed):
            flow.run(self.country, 'withdraw', self.root)
        with self.assertRaises(TransitionNotAllowed):
            flow.terminate(self.country, self.root)

    def test_the_control_view(self):
        self.flow.run(self.country, 'call', self.root)
        self.client.force_login(self.root)
        detail = reverse('flow_detail', args=[self.flow.name, self.country.pk])
        page = self.client.get(detail)
        self.assertContains(page, 'value="retry"')
        self.assertContains(page, 'data-status="error"')
        FLAKY['fail'] = False
        self.client.post(reverse('flow_control', args=[self.flow.name, 'retry',
                                                       self.country.pk]))
        self.assertEqual(self.flow.state(self.country), 'called')
        nobody = make_user('nobody', 'view_country')
        self.client.force_login(nobody)
        self.client.post(reverse('flow_control', args=[self.flow.name, 'suspend',
                                                       self.country.pk]))
        self.assertEqual(self.flow.get_instance(self.country).status, 'running')


# -- versions and JSON ----------------------------------------------------------------
def versioned_document(target):
    return {'schema_version': 2, 'name': 'tests.v2.json', 'model': 'demoapp.Country',
            'initial': 'a',
            'states': [{'id': 'a'}, {'id': target, 'label': target.upper()}],
            'transitions': [{'name': 'go', 'source': 'a', 'target': target}]}


class VersionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root = root()

    def test_old_instances_stay_in_their_version(self):
        v1 = publish_definition(versioned_document('b'))
        old = Country.objects.create(name='Old')
        get_flow('tests.v2.json').start(old)
        v2 = publish_definition(versioned_document('c'))
        self.assertEqual((v1.version, v2.version), (1, 2))
        v1.refresh_from_db()
        self.assertFalse(v1.is_active)
        new = Country.objects.create(name='New')
        flow = get_flow('tests.v2.json')
        self.assertEqual(flow.version, 2)
        self.assertEqual(flow.run(old, 'go', self.root).state, 'b')
        instance = flow.run(new, 'go', self.root)
        self.assertEqual((instance.state, instance.version, instance.definition),
                         ('c', 2, v2))
        self.assertEqual(get_flow('tests.v2.json', version=1).state_label('b'), 'B')

    def test_python_versions(self):
        old = Country.objects.create(name='Old')
        get_flow('tests.v2.versioned').start(old)
        register_flow(Version2)
        new = Country.objects.create(name='New')
        flow = get_flow('tests.v2.versioned')
        self.assertEqual(flow.version, 2)
        self.assertEqual(flow.run(old, 'go', self.root).state, 'b')
        self.assertEqual(flow.run(new, 'go', self.root).state, 'c')

    def test_invalid_documents(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "missing required 'model'"):
            build_flow({'schema_version': 2, 'name': 'x', 'initial': 'a',
                        'states': [{'id': 'a'}]})
        document = versioned_document('b')
        document['states'][1]['branches'] = ['a', 'b']
        with self.assertRaisesMessage(ImproperlyConfigured, 'does not take branches'):
            build_flow(document)
        document = versioned_document('b')
        document['transitions'][0]['actions'] = [{'action': 'nope'}]
        with self.assertRaisesMessage(ImproperlyConfigured, 'No flow action named'):
            build_flow(document)
        self.assertFalse(FlowDefinition.objects.exists())

    def test_publish_command(self):
        out = StringIO()
        call_command('gtflows_publish', str(EXPENSE_JSON), stdout=out)
        self.assertIn('demoapp.expenses_json v1', out.getvalue())
        self.assertEqual(get_flow('demoapp.expenses_json').title,
                         'Expense approval (JSON)')


class ExpenseEquivalenceTests(TestCase):
    """The expense flow declared in Python and its JSON twin behave alike."""

    FLOWS = ('demoapp.ExpenseFlow', 'demoapp.expenses_json')

    @classmethod
    def setUpTestData(cls):
        with open(EXPENSE_JSON, encoding='utf-8') as handle:
            publish_definition(json.load(handle))
        finance = Group.objects.create(name='Finance')
        cls.ana = make_user('ana', 'change_expensereport', 'view_expensereport')
        cls.boss = make_user('boss', 'view_expensereport')
        cls.money = make_user('money', groups=[finance])

    def expense(self, flow_name, amount):
        obj = ExpenseReport.objects.create(title='Trip', amount=amount,
                                           requester=self.ana, manager=self.boss,
                                           flow_name=flow_name)
        get_flow(flow_name).run(obj, 'submit', self.ana)
        return obj

    def decide(self, obj, user, outcome):
        Task.objects.inbox(user).get(object_id=str(obj.pk)).complete(user, outcome)

    def scenario(self, flow_name, name):
        flow = get_flow(flow_name)
        if name == 'small':
            obj = self.expense(flow_name, 100)
            states = [flow.state(obj)]
            self.decide(obj, self.boss, 'approve')
            states.append(flow.state(obj))
            flow.signal(obj, 'paid')
            obj.refresh_from_db()
            instance = flow.get_instance(obj)
            return states + [flow.state(obj), obj.paid,
                             instance.variables['approved_amount']]
        if name in ('large_rejected', 'large_approved'):
            obj = self.expense(flow_name, 5000)
            states = [flow.state(obj), flow.tasks(obj).count()]
            self.decide(obj, self.money, 'approve')
            states.append(flow.state(obj))
            self.decide(obj, self.boss, 'reject' if name == 'large_rejected'
                        else 'approve')
            return states + [flow.state(obj)]
        if name == 'escalated':
            obj = self.expense(flow_name, 100)
            process_due(later(days=4))
            task = flow.tasks(obj).get()
            return [task.state, task.priority,
                    list(task.groups.values_list('name', flat=True)),
                    Notification.objects.filter(user=self.money).exists()]

    def test_same_behaviour(self):
        expected = {
            'small': ['manager', 'payment', 'closed', True, '100.00'],
            'large_rejected': ['review', 2, 'review', 'rejected'],
            'large_approved': ['review', 2, 'review', 'payment'],
            'escalated': ['unassigned', 1, ['Finance'], True],
        }
        for name, result in expected.items():
            for flow_name in self.FLOWS:
                with self.subTest(flow=flow_name, scenario=name):
                    self.assertEqual(self.scenario(flow_name, name), result)

    def test_same_graph(self):
        python, loaded = (get_flow(name).as_graph() for name in self.FLOWS)
        self.assertEqual([(node['id'], node['type']) for node in python['nodes']],
                         [(node['id'], node['type']) for node in loaded['nodes']])
        self.assertEqual(sorted((e['source'], e['target']) for e in python['edges']),
                         sorted((e['source'], e['target']) for e in loaded['edges']))


# -- actions ------------------------------------------------------------------------
class ActionRegistryTests(TestCase):
    def test_from_json(self):
        action = action_from_json({'action': 'notify', 'props': {
            'message': 'Hi {{ object }}', 'to': 'actor'}})
        self.assertIsInstance(action, Notify)
        self.assertIs(get_action('set_field'), SetField)
        for name in ('set_field', 'assign', 'notify', 'send_email', 'call',
                     'create_task', 'start_flow', 'set_variable'):
            self.assertTrue(get_action(name).props_schema, name)

    def test_props_are_validated(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "missing required 'code'"):
            action_from_json({'action': 'send_email', 'props': {'to': 'x@y.org'}})
        with self.assertRaisesMessage(ImproperlyConfigured, 'unexpected property'):
            action_from_json({'action': 'set_field',
                              'props': {'field': 'a', 'bogus': 1}})

    def test_outside_a_flow(self):
        """What automations do: flow and instance are None."""
        user = make_user('ana')
        country = Country.objects.create(name='Peru')
        context = ActionContext(obj=country, user=user)
        for spec in ({'action': 'set_field', 'props': {'field': 'code', 'value': 'pe'}},
                     {'action': 'notify', 'props': {'message': '{{ object }}'}},
                     {'action': 'assign', 'props': {'user': 'actor'}},
                     {'action': 'create_task', 'props': {'title': 'Check {{ object }}',
                                                         'owners': 'actor',
                                                         'due': 'P1D'}},
                     {'action': 'start_flow', 'props': {'flow': 'tests.v2.child'}}):
            action_from_json(spec).run(context)
        country.refresh_from_db()
        self.assertEqual(country.code, 'pe')
        self.assertEqual(Notification.objects.get(user=user).description, 'Peru')
        task = Task.objects.get()
        self.assertEqual((task.title, task.instance), ('Check Peru', None))
        self.assertEqual(get_flow('tests.v2.child').state(country), 'todo')


# -- tasks ------------------------------------------------------------------------
class TaskTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.checkers = Group.objects.create(name='Checkers')
        cls.ana = make_user('ana', 'view_country')
        cls.ben = make_user('ben', 'view_country', groups=[cls.checkers])
        cls.cid = make_user('cid', 'view_country')
        cls.outsider = make_user('outsider', 'view_country')
        cls.country = Country.objects.create(name='Chile')

    def task(self, **kwargs):
        return create_task(obj=self.country, title='Check it',
                           potential_owners=[self.ana], groups=['Checkers'],
                           **kwargs)

    def test_every_state_change(self):
        task = self.task()
        self.assertEqual(task.state, Task.UNASSIGNED)
        task.claim(self.ana)
        self.assertEqual((task.state, task.actual_owner), (Task.ASSIGNED, self.ana))
        task.release(self.ana)
        self.assertEqual((task.state, task.actual_owner), (Task.UNASSIGNED, None))
        task.claim(self.ben)
        task.request_info(self.ben, self.cid, 'What is the budget?')
        self.assertEqual((task.state, task.info_from), (Task.INFO_REQUESTED, self.cid))
        self.assertIn(task, Task.objects.inbox(self.cid))
        task.submit_info(self.cid, '1000')
        self.assertEqual(task.state, Task.ASSIGNED)
        task.complete(self.ben, 'approve', 'fine', data={'score': 3})
        task.refresh_from_db()
        self.assertEqual((task.state, task.outcome, task.data),
                         (Task.COMPLETED, 'approve', {'score': 3}))
        actions = list(task.history.values_list('action', flat=True))
        self.assertEqual(actions, ['create', 'claim', 'release', 'claim',
                                   'request_info', 'submit_info', 'complete'])
        self.assertEqual(list(task.comments.values_list('text', flat=True)),
                         ['What is the budget?', '1000', 'fine'])
        self.assertNotIn(task, Task.objects.inbox(self.ben))
        cancelled = self.task()
        cancelled.cancel()
        self.assertEqual(cancelled.state, Task.CANCELLED)

    def test_only_a_potential_owner_takes_it(self):
        task = self.task()
        for user in (self.outsider, self.cid):
            with self.assertRaises(TaskNotAllowed):
                task.claim(user)
            with self.assertRaises(TaskNotAllowed):
                task.complete(user, 'approve')
        task.claim(self.ben)  # through the group
        with self.assertRaises(TaskNotAllowed):
            task.claim(self.ana)  # taken
        with self.assertRaises(TaskNotAllowed):
            task.release(self.ana)
        with self.assertRaises(TaskNotAllowed):
            task.complete(self.ben, 'maybe')  # not an outcome
        self.assertEqual(set(Task.objects.inbox(self.ana)), set())
        self.assertEqual(list(Task.objects.inbox(self.ben)), [task])

    def test_delegation(self):
        task = self.task()
        task.claim(self.ana)
        with self.assertRaises(TaskNotAllowed):
            task.delegate(self.ben, self.cid)
        task.delegate(self.ana, self.cid, 'you know it better')
        self.assertEqual(task.actual_owner, self.cid)
        self.assertNotIn(task, Task.objects.inbox(self.ana))
        task.complete(self.cid, 'reject')
        self.assertEqual(task.history.get(action='delegate').to_user, self.cid)

    def test_request_info_waits_for_the_answer(self):
        task = self.task()
        task.claim(self.ana)
        task.request_info(self.ana, self.cid, 'Why?')
        with self.assertRaises(TaskNotAllowed):
            task.complete(self.ana, 'approve')
        with self.assertRaises(TaskNotAllowed):
            task.submit_info(self.ben, 'Because')
        task.submit_info(self.cid, 'Because')
        task.complete(self.ana, 'approve')

    def test_expiry_escalates(self):
        task = self.task(due=timedelta(hours=1), priority=3, on_expire={
            'escalate': {'users': [self.cid.pk], 'groups': [], 'priority': 1,
                         'due': 3600},
            'notify': '{{ task }} is late'})
        task.claim(self.ana)
        self.assertEqual(process_due(later(minutes=30)), {})
        self.assertEqual(process_due(later(hours=2)), {'task_escalated': 1})
        task.refresh_from_db()
        self.assertEqual((task.state, task.actual_owner, task.priority),
                         (Task.UNASSIGNED, None, 1))
        self.assertEqual(list(task.potential_owners.all()), [self.cid])
        self.assertFalse(task.groups.exists())
        self.assertAlmostEqual(task.due, later(hours=3), delta=timedelta(minutes=5))
        self.assertEqual(Notification.objects.get(user=self.cid).description,
                         'Check it is late')
        self.assertEqual(task.history.last().action, 'escalate')

    def test_expiry_with_an_outcome_moves_the_flow(self):
        flow = get_flow('tests.v2.tasks')
        flow.run(self.country, 'submit_decide', root())
        process_due(later(days=2))
        self.assertEqual(flow.state(self.country), 'rejected')
        task = flow.tasks(self.country).get()
        self.assertEqual((task.state, task.outcome), (Task.COMPLETED, 'reject'))

    def test_plain_expiry_takes_the_expired_outcome(self):
        flow = get_flow('tests.v2.tasks')
        flow.run(self.country, 'submit', root())
        self.assertEqual(process_due(later(days=2)), {'task_expired': 1})
        self.assertEqual(flow.state(self.country), 'late')

    def test_signals(self):
        seen = []

        def receiver(sender, **kwargs):
            seen.append(kwargs.get('outcome', kwargs.get('new')))
        for signal in (task_created, task_completed, flow_state_changed):
            signal.connect(receiver)
        try:
            flow = get_flow('tests.v2.tasks')
            flow.run(self.country, 'submit', root())
            Task.objects.get().complete(self.ana, 'approve')
        finally:
            for signal in (task_created, task_completed, flow_state_changed):
                signal.disconnect(receiver)
        # The engine's own receiver of task_completed runs first.
        self.assertEqual(seen, ['draft', None, 'approval', 'approved', 'approve'])


class HumanTaskFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.checkers = Group.objects.create(name='Checkers')
        cls.ana = make_user('ana', 'view_country')
        cls.ben = make_user('ben', 'view_country', groups=[cls.checkers])
        cls.flow = get_flow('tests.v2.tasks')

    def test_the_outcome_routes_the_flow(self):
        country = Country.objects.create(name='Peru')
        instance = self.flow.run(country, 'submit', root())
        task = Task.objects.get()
        self.assertEqual((task.title, task.priority, task.instance, task.activity),
                         ('Approve Peru', 2, instance, 'approval'))
        self.assertEqual(task.outcome_choices, ['approve', 'reject'])
        self.assertEqual(Task.objects.inbox(self.ben).get(), task)
        task.complete(self.ben, 'reject', data={'reason': 'too dear'})
        instance.refresh_from_db()
        self.assertEqual(instance.state, 'rejected')
        self.assertEqual(instance.variables, {'reason': 'too dear',
                                              'approval_outcome': 'reject'})

    def test_leaving_by_a_transition_cancels_the_task(self):
        country = Country.objects.create(name='Peru')
        self.flow.run(country, 'submit', root())
        self.flow.run(country, 'withdraw', root())
        self.assertEqual(Task.objects.get().state, Task.CANCELLED)

    def test_a_suspended_flow_refuses_the_completion(self):
        country = Country.objects.create(name='Peru')
        self.flow.run(country, 'submit', root())
        self.flow.suspend(country)
        task = Task.objects.get()
        with self.assertRaises(TransitionNotAllowed):
            task.complete(self.ana, 'approve')
        task.refresh_from_db()
        self.assertEqual(task.state, Task.UNASSIGNED)  # undone with the flow


# English labels are asserted: the demo runs in Spanish once its .mo, which is
# not versioned, is compiled, and a local run would disagree with CI.
@override_settings(LANGUAGE_CODE='en')
class TaskInboxViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.checkers = Group.objects.create(name='Checkers')
        cls.ana = make_user('ana', 'view_country')
        cls.ben = make_user('ben', 'view_country', groups=[cls.checkers])
        cls.outsider = make_user('outsider')
        cls.country = Country.objects.create(name='Chile')
        cls.flow = get_flow('tests.v2.tasks')
        cls.flow.run(cls.country, 'submit', root())
        cls.loose = create_task(obj=cls.country, title='Loose one',
                                potential_owners=[cls.ben], priority=5)

    def setUp(self):
        self.client.force_login(self.ben)

    def test_inbox_and_filters(self):
        url = reverse('task_inbox')
        page = self.client.get(url)
        self.assertContains(page, 'Approve Chile')
        self.assertContains(page, 'Loose one')
        self.assertNotContains(self.client.get(url + '?flow=tests.v2.tasks'),
                               'Loose one')
        self.assertNotContains(self.client.get(url + '?priority=2'), 'Loose one')
        self.assertContains(self.client.get(url + '?due=none'), 'Loose one')
        self.assertNotContains(self.client.get(url + '?due=overdue'), 'Chile')
        self.assertNotContains(self.client.get(url + '?state=completed'), 'Loose')
        self.client.force_login(self.outsider)
        self.assertNotContains(self.client.get(url), 'Approve Chile')

    def test_detail_and_actions(self):
        task = Task.objects.get(activity='approval')
        detail = reverse('task_detail', args=[task.pk])
        self.assertContains(self.client.get(detail), 'name="task-claim"')

        def action(name):
            return reverse('task_action', args=[task.pk, name])
        self.client.post(action('claim'))
        self.client.post(action('comment'), {'comment-text': 'Looking at it'})
        self.client.post(action('request_info'), {
            'request_info-to_user': self.ana.pk,
            'request_info-comment': 'Is it urgent?'})
        task.refresh_from_db()
        self.assertEqual(task.state, Task.INFO_REQUESTED)
        self.client.force_login(self.ana)
        self.client.post(action('submit_info'), {'submit_info-comment': 'Yes'})
        self.client.force_login(self.ben)
        page = self.client.get(detail)
        self.assertContains(page, 'Is it urgent?')
        self.assertContains(page, 'value="approve"')
        response = self.client.post(action('complete'), {
            'outcome': 'approve', 'complete-comment': 'ok'})
        self.assertRedirects(response, reverse('task_inbox'),
                             fetch_redirect_response=False)
        self.assertEqual(self.flow.state(self.country), 'approved')

    def test_refusals(self):
        task = Task.objects.get(activity='approval')
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse('task_detail', args=[task.pk])
                                         ).status_code, 404)
        self.client.force_login(self.ana)
        self.client.post(reverse('task_action', args=[task.pk, 'claim']))
        self.client.force_login(self.ben)
        page = self.client.post(reverse('task_action', args=[task.pk, 'complete']),
                                {'outcome': 'approve'}, follow=True)
        self.assertContains(page, 'You cannot')
        self.assertEqual(self.flow.state(self.country), 'approval')


class RuntimeDiagramTests(TestCase):
    def test_active_completed_and_error(self):
        flow = get_flow('tests.v2.activities')
        country = Country.objects.create(name='Chile')
        FLAKY['fail'] = True
        instance = flow.run(country, 'call', root())
        runtime = flow.runtime(instance)
        self.assertEqual((runtime['error'], runtime['completed']), (['call'],
                                                                    ['start']))
        svg = render_svg(flow.as_graph(), runtime=runtime)
        self.assertIn('data-state="call" data-type="action" data-status="error"', svg)
        self.assertIn('data-state="start" data-type="state" data-status="completed"',
                      svg)
        parallel = get_flow('tests.v2.parallel')
        country = Country.objects.create(name='Peru')
        parallel.run(country, 'start', root())
        parallel.run(country, 'ok_tech', root())
        runtime = parallel.runtime(parallel.get_instance(country))
        self.assertEqual(sorted(runtime['active']), ['all_done', 'legal', 'money'])
        self.assertIn('split', runtime['completed'])


# -- concurrency -------------------------------------------------------------------
@skipUnless(connection.vendor == 'postgresql',
            'needs row locks: SQLite serializes the whole database')
class TaskConcurrencyTests(TransactionTestCase):
    def test_two_users_cannot_complete_the_same_task(self):
        checkers = Group.objects.create(name='Checkers')
        users = [make_user(name, groups=[checkers]) for name in ('ana', 'ben')]
        country = Country.objects.create(name='Chile')
        flow = get_flow('tests.v2.tasks')
        flow.run(country, 'submit_decide', root())
        task_pk = Task.objects.get().pk
        barrier = threading.Barrier(2)
        results = []

        def complete(user):
            try:
                task = Task.objects.get(pk=task_pk)
                barrier.wait()
                task.complete(user, 'approve')
                results.append('done')
            except TaskNotAllowed:
                results.append('refused')
            finally:
                connection.close()

        threads = [threading.Thread(target=complete, args=(user,)) for user in users]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(results), ['done', 'refused'])
        task = Task.objects.get(pk=task_pk)
        self.assertEqual(task.history.filter(action='complete').count(), 1)
        self.assertEqual(flow.state(country), 'approved')
        self.assertEqual(flow.history(country).filter(kind='task').count(), 1)
