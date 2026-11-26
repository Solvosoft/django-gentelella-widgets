"""W21: ``Flow.run(..., system=True)`` runs a transition as the system, the
way automatic transitions and deadlines do: no permission is checked, the
source state and the condition are; and nobody gets there by accident --
``user=None`` or an anonymous user without the flag are refused as before."""

import inspect
from decimal import Decimal

from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase, override_settings

from demoapp.models import Product
from djgentelella.flows.base import Flow, Transition, register_flow
from djgentelella.flows.exceptions import TransitionBlocked, TransitionNotAllowed
from djgentelella.flows.models import FlowTransitionLog

__all__ = ['SystemRunTests']

FLOW = 'tests.w21.system'


def has_a_price(context):
    return context.obj.price > 0


class SystemFlow(Flow):
    name = FLOW
    model = Product
    states = [('draft', 'Draft'), ('ready', 'Ready'), ('done', 'Done')]
    initial = 'draft'
    transitions = [
        Transition('prepare', 'draft', 'ready', label='Prepare',
                   perms=['demoapp.change_product'], condition=has_a_price),
        Transition('close', 'ready', 'done', label='Close',
                   perms=['demoapp.delete_product']),
    ]


register_flow(SystemFlow)


@override_settings(LANGUAGE_CODE='en',
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SystemRunTests(TestCase):
    def setUp(self):
        self.flow = SystemFlow()
        self.obj = Product.objects.create(name='Pear', price=Decimal('3.00'))
        self.user = User.objects.create_user('nobody', password='pw')

    def state(self):
        return self.flow.state(self.obj)

    def test_start_without_a_user_is_a_start_by_the_system(self):
        instance = self.flow.start(self.obj)
        self.assertEqual(instance.state, 'draft')

    def test_a_system_run_checks_no_permission(self):
        instance = self.flow.run(self.obj, 'prepare', system=True)
        self.assertEqual(instance.state, 'ready')
        log = FlowTransitionLog.objects.get(transition='prepare')
        self.assertIsNone(log.user)
        # A user without the permissions cannot, as before.
        with self.assertRaises(TransitionNotAllowed):
            self.flow.run(self.obj, 'close', self.user)
        self.flow.run(self.obj, 'close', system=True)
        self.assertEqual(self.state(), 'done')

    def test_a_system_run_checks_the_condition(self):
        Product.objects.filter(pk=self.obj.pk).update(price=Decimal('0'))
        with self.assertRaises(TransitionBlocked):
            self.flow.run(self.obj, 'prepare', system=True)
        self.assertEqual(self.state(), 'draft')

    def test_a_system_run_checks_the_state(self):
        with self.assertRaises(TransitionNotAllowed):
            self.flow.run(self.obj, 'close', system=True)
        self.assertEqual(self.state(), 'draft')

    def test_no_user_without_the_flag_is_refused(self):
        for user in (None, AnonymousUser()):
            with self.subTest(user=user):
                with self.assertRaises(TransitionNotAllowed):
                    self.flow.run(self.obj, 'prepare', user)
                with self.assertRaises(TransitionNotAllowed):
                    self.flow.run(self.obj, 'prepare')
        self.assertEqual(self.state(), 'draft')
        self.assertFalse(FlowTransitionLog.objects.filter(transition='prepare')
                         .exists())

    def test_the_flag_takes_no_user(self):
        # A request's user -- signed in or anonymous -- never runs as the
        # system by passing the flag along with it.
        for user in (self.user, AnonymousUser()):
            with self.subTest(user=user):
                with self.assertRaises(ValueError):
                    self.flow.run(self.obj, 'prepare', user, system=True)
        self.assertEqual(self.state(), 'draft')

    def test_the_flag_is_keyword_only(self):
        # A True in any positional slot can never turn on the system run.
        parameter = inspect.signature(self.flow.run).parameters['system']
        self.assertIs(parameter.kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertIs(parameter.default, False)
        positional = [name for name, found in
                      inspect.signature(self.flow.run).parameters.items()
                      if found.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD]
        with self.assertRaises(TypeError):
            self.flow.run(self.obj, 'prepare',
                          *[None] * (len(positional) - 2), True)
        self.assertEqual(self.state(), 'draft')
