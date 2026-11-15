"""The engine's second round: hooks and signals, blocking reasons, automatic
transitions, deadlines, quorum approvals (human tasks), claiming, bulk runs and
the diagram.
"""

from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.template import Context, Template
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from demoapp.models import Country
from djgentelella.flows import (
    ANY_STATE,
    Action,
    Assign,
    Deadline,
    Flow,
    HumanTask,
    Transition,
    TransitionBlocked,
    TransitionNotAllowed,
    get_flow,
    post_transition,
    pre_transition,
    register_flow,
)
from djgentelella.flows.diagram import collapse_any, render_svg
from djgentelella.flows.models import FlowInstance, FlowTransitionLog, Task
from djgentelella.flows.timers import process_due

ORDER = []


class Mark(Action):
    def __init__(self, tag):
        self.tag = tag

    def run(self, context):
        ORDER.append(self.tag)


def make_user(name, *codenames, groups=()):
    user = get_user_model().objects.create_user(name, password='x')
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
    for group in groups:
        user.groups.add(group)
    return user


def root():
    return get_user_model().objects.create_superuser('root', password='x')


# -- hooks and signals ---------------------------------------------------------
@register_flow
class HookFlow(Flow):
    name = 'tests.hooks'
    model = Country
    states = [('a', 'A'), ('b', 'B'), ('c', 'C')]
    initial = 'a'
    on_exit = {'a': [Mark('exit a')]}
    on_enter = {'b': [Mark('enter b')]}
    transitions = [
        Transition('go', 'a', 'b', actions=[Mark('go')]),
        Transition('stay', 'b', 'b', actions=[Mark('stay')]),
        Transition('end', 'b', 'c'),
        Transition('edit', 'a', 'b', form=object),  # never bulk: it has a form
    ]


class HookTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.flow = get_flow('tests.hooks')
        cls.root = root()
        cls.country = Country.objects.create(name='Chile')

    def setUp(self):
        ORDER.clear()

    def test_exit_transition_enter(self):
        self.flow.run(self.country, 'go', self.root)
        self.assertEqual(ORDER, ['exit a', 'go', 'enter b'])
        ORDER.clear()
        self.flow.run(self.country, 'stay', self.root)
        self.assertEqual(ORDER, ['stay'])  # not left, not entered

    def test_signals(self):
        seen = []

        def receiver(sender, **kwargs):
            seen.append((sender, kwargs['source'], kwargs['target'], kwargs['kind']))
        pre_transition.connect(receiver, sender=HookFlow)
        post_transition.connect(receiver, sender=HookFlow)
        try:
            self.flow.run(self.country, 'go', self.root)
        finally:
            pre_transition.disconnect(receiver, sender=HookFlow)
            post_transition.disconnect(receiver, sender=HookFlow)
        self.assertEqual(seen, [(HookFlow, 'a', 'b', 'transition')] * 2)

    def test_a_receiver_that_raises_undoes_it(self):
        def receiver(sender, **kwargs):
            raise RuntimeError('no')
        post_transition.connect(receiver, sender=HookFlow)
        try:
            with self.assertRaises(RuntimeError):
                self.flow.run(self.country, 'go', self.root)
        finally:
            post_transition.disconnect(receiver, sender=HookFlow)
        self.assertEqual(self.flow.state(self.country), 'a')

    def test_hooks_on_unknown_states_are_refused(self):
        class Broken(Flow):
            model = Country
            states = [('a', 'A')]
            initial = 'a'
            on_enter = {'z': []}
        with self.assertRaises(ImproperlyConfigured):
            Broken()


# -- blocking reasons --------------------------------------------------------------
def needs_code(context):
    if not context.obj.code:
        raise TransitionBlocked('It needs a code first.')
    return True


@register_flow
class BlockedFlow(Flow):
    name = 'tests.blocked'
    model = Country
    states = [('draft', 'Draft'), ('done', 'Done')]
    initial = 'draft'
    transitions = [Transition('publish', 'draft', 'done', label='Publish',
                              perms=['demoapp.change_country'], condition=needs_code)]


class BlockedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.flow = get_flow('tests.blocked')
        cls.editor = make_user('editor', 'change_country', 'view_country')
        cls.nobody = make_user('nobody', 'view_country')
        cls.country = Country.objects.create(name='Chile')

    def test_the_reason_is_on_a_disabled_button(self):
        [button] = self.flow.transition_buttons(self.country, self.editor)
        self.assertEqual((button.disabled, button.reason),
                         (True, 'It needs a code first.'))
        # Without the permission, the transition is not shown at all.
        self.assertEqual(self.flow.transition_buttons(self.country, self.nobody), [])
        self.client.force_login(self.editor)
        page = self.client.get(reverse('flow_detail', args=[self.flow.name,
                                                            self.country.pk]))
        self.assertContains(page, 'title="It needs a code first."')
        self.assertContains(page, 'disabled')

    def test_running_it_gives_the_reason(self):
        with self.assertRaisesMessage(TransitionBlocked, 'It needs a code first.'):
            self.flow.run(self.country, 'publish', self.editor)
        self.country.code = 'cl'
        self.country.save()
        [button] = self.flow.transition_buttons(self.country, self.editor)
        self.assertFalse(button.disabled)
        self.flow.run(self.country, 'publish', self.editor)


# -- automatic transitions -------------------------------------------------------
@register_flow
class AutoFlow(Flow):
    name = 'tests.auto'
    model = Country
    states = [('new', 'New'), ('check', 'Check'), ('small', 'Small'), ('big', 'Big'),
              ('loop1', 'Loop 1'), ('loop2', 'Loop 2')]
    initial = 'new'
    transitions = [
        Transition('submit', 'new', 'check'),
        Transition('fast', 'new', 'check', auto=True,
                   condition=lambda context: context.obj.code == 'go'),
        Transition('to_small', 'check', 'small', auto=True,
                   condition=lambda context: len(context.obj.name) < 5),
        Transition('to_big', 'check', 'big', auto=True),
        Transition('spin', 'big', 'loop1'),
        Transition('l1', 'loop1', 'loop2', auto=True),
        Transition('l2', 'loop2', 'loop1', auto=True),
    ]


class AutoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.flow = get_flow('tests.auto')
        cls.root = root()

    def test_the_first_true_condition_wins(self):
        peru = Country.objects.create(name='Peru')
        chile = Country.objects.create(name='Costa Rica')
        self.assertEqual(self.flow.run(peru, 'submit', self.root).state, 'small')
        self.assertEqual(self.flow.run(chile, 'submit', self.root).state, 'big')
        kinds = list(self.flow.history(peru).values_list('kind', 'transition'))
        self.assertEqual(kinds, [('auto', 'to_small'), ('transition', 'submit')])

    def test_a_loop_is_stopped_and_undone(self):
        country = Country.objects.create(name='Costa Rica')
        self.flow.run(country, 'submit', self.root)
        with self.assertRaises(ImproperlyConfigured):
            self.flow.run(country, 'spin', self.root)
        self.assertEqual(self.flow.state(country), 'big')

    def test_automatic_transitions_are_not_buttons(self):
        country = Country.objects.create(name='Peru')
        buttons = self.flow.transition_buttons(country, self.root)
        names = [button.name for button in buttons]
        self.assertEqual(names, ['submit'])
        self.client.force_login(self.root)
        url = reverse('flow_transition', args=[self.flow.name, 'fast', country.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_evaluate(self):
        country = Country.objects.create(name='Peru', code='go')
        self.assertEqual(self.flow.evaluate(country).state, 'small')
        self.assertIsNone(self.flow.history(country).first().user)


# -- deadlines ----------------------------------------------------------------------
@register_flow
class DeadlineFlow(Flow):
    name = 'tests.deadlines'
    model = Country
    states = [('new', 'New'), ('open', 'Open'), ('escalated', 'Escalated'),
              ('waiting', 'Waiting')]
    initial = 'new'
    deadlines = {
        'open': Deadline(timedelta(hours=1), transition='escalate',
                         actions=[Mark('reminder')]),
        'waiting': Deadline(timedelta(minutes=5), actions=[Mark('nudge')]),
    }
    transitions = [
        Transition('start', 'new', 'open'),
        Transition('wait', 'new', 'waiting'),
        # Without a way out 'waiting' would be final: the instance completes
        # there, and a completed instance runs no timers.
        Transition('resume', 'waiting', 'open'),
        # The system runs it on the deadline, whatever its perms.
        Transition('escalate', 'open', 'escalated', perms=['demoapp.delete_country']),
    ]


class DeadlineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.flow = get_flow('tests.deadlines')
        cls.root = root()
        cls.country = Country.objects.create(name='Chile')

    def setUp(self):
        ORDER.clear()

    def later(self, **delta):
        return timezone.now() + timedelta(**delta)

    def test_entering_sets_the_due_date(self):
        instance = self.flow.run(self.country, 'start', self.root)
        self.assertAlmostEqual(instance.due_at, self.later(hours=1),
                               delta=timedelta(minutes=1))
        self.assertEqual(instance.visit, 1)
        self.assertIsNotNone(instance.entered_at)

    def test_a_deadline_escalates_as_the_system(self):
        self.flow.run(self.country, 'start', self.root)
        self.assertEqual(process_due(self.later(minutes=30)), {})
        self.assertEqual(process_due(self.later(hours=2)), {'moved': 1})
        instance = self.flow.get_instance(self.country)
        self.assertEqual((instance.state, instance.due_at), ('escalated', None))
        log = self.flow.history(self.country).first()
        self.assertEqual((log.kind, log.user), ('timeout', None))
        self.assertEqual(ORDER, ['reminder'])
        self.assertEqual(process_due(self.later(hours=3)), {})

    def test_a_reminder_fires_once(self):
        self.flow.run(self.country, 'wait', self.root)
        self.assertEqual(process_due(self.later(hours=1)), {'reminded': 1})
        self.assertEqual(process_due(self.later(hours=2)), {})
        self.assertEqual((self.flow.state(self.country), ORDER), ('waiting', ['nudge']))

    def test_the_command(self):
        self.flow.run(self.country, 'start', self.root)
        FlowInstance.objects.update(due_at=self.later(minutes=-1))
        out = StringIO()
        call_command('process_flow_timers', '--dry-run', stdout=out)
        self.assertIn('1 due', out.getvalue())
        self.assertEqual(self.flow.state(self.country), 'open')
        call_command('process_flow_timers', stdout=out)
        self.assertIn('moved: 1', out.getvalue())
        self.assertEqual(self.flow.state(self.country), 'escalated')

    def test_overdue_in_the_inbox(self):
        self.flow.run(self.country, 'start', self.root)
        other = Country.objects.create(name='Peru')
        self.flow.run(other, 'start', self.root)
        FlowInstance.objects.filter(object_id=str(other.pk)).update(
            due_at=self.later(minutes=-1))
        self.client.force_login(self.root)
        url = reverse('flow_inbox', args=[self.flow.name])
        self.assertContains(self.client.get(url), 'bg-danger', count=1)
        overdue = self.client.get(url + '?overdue=1')
        self.assertContains(overdue, 'Peru')
        self.assertNotContains(overdue, 'Chile')

    def test_a_deadline_must_leave_its_state(self):
        class Broken(Flow):
            model = Country
            states = [('a', 'A'), ('b', 'B')]
            initial = 'a'
            deadlines = {'a': Deadline(timedelta(days=1), transition='back')}
            transitions = [Transition('back', 'b', 'a')]
        with self.assertRaises(ImproperlyConfigured):
            Broken()


# -- quorum ------------------------------------------------------------------------
@register_flow
class QuorumFlow(Flow):
    name = 'tests.quorum'
    model = Country
    states = [('draft', 'Draft'),
              HumanTask('review', 'Review', title='Approve {{ object }}',
                        groups=['Committee'], each=True, min=2,
                        outcomes={'approve': 'approved', 'reject': 'rejected'}),
              ('approved', 'Approved'), ('rejected', 'Rejected')]
    initial = 'draft'
    transitions = [
        Transition('submit', 'draft', 'review', label='Submit'),
        Transition('reopen', ['approved', 'rejected'], 'draft'),
    ]


class QuorumTests(TestCase):
    """Approval and FlowVote are gone: a quorum is a human task with one task
    per approver."""

    @classmethod
    def setUpTestData(cls):
        cls.flow = get_flow('tests.quorum')
        committee = Group.objects.create(name='Committee')
        cls.ana = make_user('ana', 'view_country', groups=[committee])
        cls.ben = make_user('ben', 'view_country', groups=[committee])
        cls.cid = make_user('cid', 'view_country', groups=[committee])
        cls.outsider = make_user('outsider', 'view_country')
        cls.root = root()
        cls.country = Country.objects.create(name='Chile')

    def task(self, user):
        return Task.objects.inbox(user).get()

    def test_every_member_gets_a_task(self):
        self.flow.run(self.country, 'submit', self.root)
        self.assertEqual(self.flow.tasks(self.country).count(), 3)
        self.assertEqual(Task.objects.inbox(self.outsider).count(), 0)
        with self.assertRaises(Exception):
            self.task(self.ana).complete(self.outsider, 'approve')

    def test_the_quorum_moves_it(self):
        self.flow.run(self.country, 'submit', self.root)
        self.task(self.ana).complete(self.ana, 'approve')
        self.assertEqual(self.flow.state(self.country), 'review')
        self.task(self.ben).complete(self.ben, 'approve')
        instance = self.flow.get_instance(self.country)
        self.assertEqual(instance.state, 'approved')
        self.assertEqual(instance.variables['review_outcome'], 'approve')
        # cid's task is no longer needed.
        self.assertEqual(Task.objects.get(potential_owners=self.cid).state,
                         Task.CANCELLED)

    def test_a_veto_once_the_quorum_is_out_of_reach(self):
        self.flow.run(self.country, 'submit', self.root)
        self.task(self.ana).complete(self.ana, 'reject')
        self.assertEqual(self.flow.state(self.country), 'review')
        self.task(self.ben).complete(self.ben, 'reject')
        self.assertEqual(self.flow.state(self.country), 'rejected')

    def test_coming_back_starts_the_vote_over(self):
        self.flow.run(self.country, 'submit', self.root)
        self.task(self.ana).complete(self.ana, 'reject')
        self.task(self.ben).complete(self.ben, 'reject')
        self.flow.run(self.country, 'reopen', self.root)
        self.flow.run(self.country, 'submit', self.root)
        self.assertEqual(Task.objects.inbox(self.ana).count(), 1)
        self.assertEqual(self.flow.tasks(self.country).open().count(), 3)


# -- claim, release, reassign ----------------------------------------------------
@register_flow
class DeskFlow(Flow):
    name = 'tests.desk'
    model = Country
    states = [('new', 'New'), ('queue', 'Queue'), ('done', 'Done')]
    initial = 'new'
    transitions = [
        Transition('queue', 'new', 'queue', actions=[Assign(group='Desk')]),
        Transition('done', 'queue', 'done'),
    ]


class AssignmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.flow = get_flow('tests.desk')
        desk = Group.objects.create(name='Desk')
        cls.desk = desk
        cls.ana = make_user('ana', 'view_country', groups=[desk])
        cls.ben = make_user('ben', 'view_country', groups=[desk])
        cls.outsider = make_user('outsider', 'view_country')
        cls.root = root()
        cls.country = Country.objects.create(name='Chile')

    def setUp(self):
        self.flow.run(self.country, 'queue', self.root)

    def test_claim_and_release(self):
        with self.assertRaises(TransitionNotAllowed):
            self.flow.claim(self.country, self.outsider)
        instance = self.flow.claim(self.country, self.ana)
        self.assertEqual((instance.assigned_to, instance.assigned_group),
                         (self.ana, self.desk))
        with self.assertRaises(TransitionNotAllowed):
            self.flow.claim(self.country, self.ben)
        with self.assertRaises(TransitionNotAllowed):
            self.flow.release(self.country, self.ben)
        self.assertIsNone(self.flow.release(self.country, self.ana).assigned_to)
        kinds = list(self.flow.history(self.country).values_list('kind', flat=True))
        self.assertEqual(kinds, ['release', 'claim', 'transition'])

    def test_reassign_needs_its_permission(self):
        with self.assertRaises(TransitionNotAllowed):
            self.flow.reassign(self.country, self.ana, to_user=self.ben)
        instance = self.flow.reassign(self.country, self.root, to_user=self.ben)
        self.assertEqual((instance.assigned_to, instance.assigned_group),
                         (self.ben, None))
        self.assertEqual(self.flow.history(self.country).first().data,
                         {'to_user': 'ben', 'to_group': None})

    def test_the_views(self):
        self.client.force_login(self.ana)
        detail = reverse('flow_detail', args=[self.flow.name, self.country.pk])
        self.assertContains(self.client.get(detail), '>Claim</button>')
        self.client.post(reverse('flow_assign', args=[self.flow.name, 'claim',
                                                      self.country.pk]))
        self.assertEqual(self.flow.get_instance(self.country).assigned_to, self.ana)
        reassign = reverse('flow_assign', args=[self.flow.name, 'reassign',
                                                self.country.pk])
        self.client.get(reassign)  # refused: a message, no form
        self.client.force_login(self.root)
        self.assertContains(self.client.get(reassign), 'flow_assign-to_user')
        self.client.post(reassign, {'flow_assign-to_group': self.desk.pk})
        instance = self.flow.get_instance(self.country)
        self.assertEqual((instance.assigned_to, instance.assigned_group),
                         (None, self.desk))


# -- bulk ---------------------------------------------------------------------------
class BulkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.flow = get_flow('tests.hooks')
        cls.root = root()
        cls.chile = Country.objects.create(name='Chile')
        cls.peru = Country.objects.create(name='Peru')

    def test_run_many(self):
        self.flow.run(self.peru, 'go', self.root)
        result = self.flow.run_many([self.chile, self.peru], 'go', self.root)
        self.assertEqual(result.done, [self.chile])
        self.assertEqual([obj for obj, _reason in result.refused], [self.peru])
        with self.assertRaises(TransitionNotAllowed):
            self.flow.run_many([self.chile], 'edit', self.root)

    def test_bulk_transitions(self):
        self.assertEqual([t.name for t in self.flow.bulk_transitions(self.root)],
                         ['go', 'stay', 'end'])

    def test_the_inbox_form(self):
        self.client.force_login(self.root)
        inbox = reverse('flow_inbox', args=[self.flow.name])
        self.assertContains(self.client.get(inbox), 'name="objects"')
        page = self.client.post(reverse('flow_bulk', args=[self.flow.name]), {
            'transition': 'go', 'objects': [self.chile.pk, self.peru.pk, 'junk']},
            follow=True)
        self.assertContains(page, 'Done for 2.')
        self.assertEqual(self.flow.states_for([self.chile, self.peru]),
                         {self.chile.pk: 'b', self.peru.pk: 'b'})
        self.assertEqual(FlowTransitionLog.objects.count(), 2)


# -- diagram -------------------------------------------------------------------------
class DiagramTests(TestCase):
    def test_the_graph_expands_any_state(self):
        graph = get_flow('tests.things').as_graph()
        archive = sorted(edge['source'] for edge in graph['edges']
                         if edge['name'] == 'archive')
        self.assertEqual(archive, ['closed', 'new', 'open'])
        final = [node['id'] for node in graph['nodes'] if node['final']]
        self.assertEqual(final, ['archived'])
        self.assertEqual(ANY_STATE, '*')

    def test_deadlines_and_autos_are_marked(self):
        edges = {edge['name']: edge for edge in get_flow('tests.deadlines'
                                                         ).as_graph()['edges']}
        self.assertTrue(edges['escalate']['timeout'])
        auto = {edge['name']: edge for edge in get_flow('tests.auto'
                                                        ).as_graph()['edges']}
        self.assertTrue(auto['to_big']['auto'])

    def test_svg(self):
        svg = render_svg(get_flow('tests.quorum').as_graph(), current='approved')
        self.assertIn('class="gt-flow-node current" data-state="approved"', svg)
        self.assertIn('>approve</tspan>', svg)
        self.assertIn('class="gt-flow-node initial" data-state="draft"', svg)
        self.assertIn('class="gt-flow-node human_task" data-state="review" '
                      'data-type="human_task"', svg)

    def test_any_state_is_one_node(self):
        graph = collapse_any(get_flow('tests.things').as_graph())
        archive = [edge for edge in graph['edges'] if edge['name'] == 'archive']
        self.assertEqual([(edge['source'], edge['target']) for edge in archive],
                         [('*', 'archived')])
        svg = render_svg(get_flow('tests.things').as_graph())
        self.assertIn('class="gt-flow-node any" data-state="*"', svg)
        self.assertIn('>Any state</text>', svg)

    def test_parallel_edges_stack_their_labels(self):
        svg = render_svg(get_flow('tests.auto').as_graph())
        # submit and fast both go new -> check: one path, two lines.
        self.assertIn('>Submit</tspan><tspan x="', svg)
        self.assertIn('dy="14">Fast</tspan>', svg)

    def test_view_and_tag(self):
        self.client.force_login(root())
        url = reverse('flow_diagram', args=['tests.quorum'])
        self.assertContains(self.client.get(url), '<svg')
        self.assertEqual(self.client.get(url + '?format=json').json()['nodes'][0]['id'],
                         'draft')
        country = Country.objects.create(name='Chile')
        html = Template("{% load gtflows %}{% flow_diagram 'tests.quorum' country %}"
                        ).render(Context({'country': country}))
        self.assertIn('initial active', html)
