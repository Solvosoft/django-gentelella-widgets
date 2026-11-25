"""Limits of the flow engine: a ``Wait`` needs somewhere to go, long chains of
automatic activities run without exhausting the Python stack, loops are
reported as such, and subflows that start each other stop at a depth."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

from demoapp.models import Country
from djgentelella.flows import (
    ActionActivity,
    Flow,
    SetVariable,
    Subflow,
    Switch,
    Transition,
    Wait,
    build_flow,
    publish_definition,
    register_flow,
)
from djgentelella.flows.models import FlowDefinition, FlowInstance

#: Each test signs users in: a fast hasher keeps it from spending seconds
#: per test hashing their passwords (PBKDF2).
FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']


def root():
    found = get_user_model().objects.filter(username='root').first()
    return found or get_user_model().objects.create_superuser('root', password='x')


def wait_document(**wait):
    return {'schema_version': 2, 'name': 'tests.limits.wait_json',
            'model': 'demoapp.Country', 'initial': 'a',
            'states': [{'id': 'a'}, dict({'id': 'w', 'type': 'wait'}, **wait),
                       {'id': 'b'}],
            'transitions': [{'name': 'go', 'source': 'a', 'target': 'w'}]}


class WaitNeedsNextTests(TestCase):
    """The signal and the timeout both move the token to ``next``: without
    it the signal raised a KeyError and the timer retried forever."""

    def test_python_wait_without_next(self):
        for kwargs in ({'signal': 'paid'}, {'after': timedelta(hours=1)},
                       {'until': 'deadline'}):
            with self.subTest(**kwargs), self.assertRaisesMessage(
                    ImproperlyConfigured, "Wait 'w' has no next activity"):
                Wait('w', **kwargs)

    def test_json_wait_without_next_is_refused(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'has no next activity'):
            build_flow(wait_document(signal='paid'))
        with self.assertRaisesMessage(ImproperlyConfigured, 'has no next activity'):
            publish_definition(wait_document(after='PT1H'))
        self.assertFalse(FlowDefinition.objects.exists())

    def test_json_wait_with_next(self):
        flow = build_flow(wait_document(signal='paid', next='b'))
        country = Country.objects.create(name='Chile')
        flow.run(country, 'go', root())
        self.assertEqual(flow.signal(country, 'paid'), 1)
        self.assertEqual(flow.state(country), 'b')


def chain_flow(length):
    """``length`` action activities in a row, all automatic."""

    class Chain(Flow):
        name = 'tests.limits.chain'
        model = Country
        states = [('start', 'Start')] + [
            ActionActivity('step%d' % number,
                           actions=[SetVariable('last', number)],
                           next='step%d' % (number + 1) if number + 1 < length
                           else 'end')
            for number in range(length)] + [('end', 'End')]
        initial = 'start'
        transitions = [Transition('go', 'start', 'step0')]
    return Chain()


class LoopFlow(Flow):
    name = 'tests.limits.loop'
    model = Country
    states = [('start', 'Start'), Switch('ping', default='pong'),
              Switch('pong', default='ping')]
    initial = 'start'
    transitions = [Transition('go', 'start', 'ping')]


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class AutomaticChainTests(TestCase):
    """Each move used to nest a few Python frames, so a long chain hit
    RecursionError before ``Run.MAX_STEPS``."""

    def test_a_long_chain_completes(self):
        # Under MAX_STEPS (500); a few frames per move would be well past
        # Python's default recursion limit (1000).
        length = 400
        flow = chain_flow(length)
        country = Country.objects.create(name='Chile')
        instance = flow.run(country, 'go', root())
        self.assertEqual((instance.state, instance.status),
                         ('end', FlowInstance.COMPLETED))
        self.assertEqual(instance.variables['last'], length - 1)

    def test_a_loop_of_automatic_activities_is_reported(self):
        country = Country.objects.create(name='Chile')
        with self.assertRaisesMessage(
                ImproperlyConfigured, 'more than 500 moves in one run'):
            LoopFlow().run(country, 'go', root())
        # The whole run was undone.
        self.assertEqual(LoopFlow().state(country), 'start')


def new_country(context):
    return Country.objects.create(name='%s+' % context.obj.name)


@register_flow
class PingFlow(Flow):
    name = 'tests.limits.ping'
    model = Country
    states = [Subflow('call', flow='tests.limits.pong', obj=new_country,
                      next='done'), ('done', 'Done')]
    initial = 'call'
    transitions = []


@register_flow
class PongFlow(Flow):
    name = 'tests.limits.pong'
    model = Country
    states = [Subflow('call', flow='tests.limits.ping', obj=new_country,
                      next='done'), ('done', 'Done')]
    initial = 'call'
    transitions = []


class SubflowDepthTests(TestCase):
    """A -> B -> A on new objects each time used to recurse until Python
    gave up; the depth is capped by GT_FLOWS_MAX_SUBFLOW_DEPTH."""

    def chain(self):
        country = Country.objects.create(name='C')
        root = PingFlow().start(country)
        found = [root]
        while True:
            child = FlowInstance.objects.filter(parent=found[-1]).first()
            if child is None:
                return found
            found.append(child)

    def test_default_depth(self):
        found = self.chain()
        self.assertEqual(len(found), 11)  # the root and 10 nested subflows
        deepest = found[-1]
        self.assertEqual(deepest.status, FlowInstance.ERROR)
        self.assertIn('more than 10 nested subflows', deepest.error)
        self.assertTrue(all(instance.status == FlowInstance.RUNNING
                            for instance in found[:-1]))

    @override_settings(GT_FLOWS_MAX_SUBFLOW_DEPTH=2)
    def test_configured_depth(self):
        found = self.chain()
        self.assertEqual(len(found), 3)
        self.assertIn('more than 2 nested subflows', found[-1].error)
