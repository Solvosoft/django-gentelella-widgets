"""Callables a JSON flow may name: GT_FLOWS_ALLOWED_CALLABLES and
register_callable."""
from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.utils import translation

from demoapp.models import Country
from djgentelella.flows import get_flow
from djgentelella.flows.actions import ActionContext, CallFunction, action_from_json
from djgentelella.flows.base import Flow, Transition
from djgentelella.flows.callables import (
    CallableNotAllowed,
    guard_action,
    is_allowed,
    register_callable,
    unregister_callable,
    validate_callables,
)
from djgentelella.flows.definitions import build_flow, publish_definition
from djgentelella.flows.models import FlowDefinition, FlowTransitionLog
from djgentelella.tests.FlowsV2_Test import root

CALLS = []
HERE = __name__


def record(context):
    CALLS.append(context.obj.pk)


def yes(context):
    return True


class NoteForm(forms.Form):
    note = forms.CharField(required=False)


def document(**transition):
    return {'schema_version': 2, 'name': 'tests.allowlist.allowlist',
            'model': 'demoapp.Country', 'initial': 'a',
            'states': [{'id': 'a'}, {'id': 'b'}],
            'transitions': [{'name': 'go', 'source': 'a', 'target': 'b',
                             **transition}]}


def call(path):
    return {'actions': [{'action': 'call', 'props': {'function': path}}]}


def store(doc):
    """A stored definition that skipped publishing (an old row, a bulk
    load): what the engine must still refuse when it runs."""
    return FlowDefinition.objects.create(name=doc['name'], version=1,
                                         document=doc, is_active=True)


class AllowlistTests(TestCase):
    def setUp(self):
        # The messages are compared in English, catalog compiled or not.
        self.enterContext(translation.override('en'))
        CALLS.clear()
        self.root = root()
        self.country = Country.objects.create(name='Allowlist')

    def test_nothing_is_allowed_by_default(self):
        self.assertFalse(is_allowed(HERE + '.record'))
        self.assertFalse(is_allowed('os.system'))
        self.assertFalse(is_allowed(''))
        self.assertFalse(is_allowed(None))

    @override_settings(GT_FLOWS_ALLOWED_CALLABLES=['djgentelella.tests.'
                                                   'FlowsAllowlist_Test.record',
                                                   'demoapp.flowdemos'])
    def test_paths_and_prefixes_of_the_setting(self):
        self.assertTrue(is_allowed(HERE + '.record'))
        self.assertFalse(is_allowed(HERE + '.recorder'))
        self.assertTrue(is_allowed('demoapp.flowdemos.seed.anything'))
        self.assertFalse(is_allowed('demoapp.flowdemosx.y'))

    def test_registered_callables_and_conditions(self):
        register_callable(record)
        self.addCleanup(unregister_callable, HERE + '.record')
        self.assertTrue(is_allowed(HERE + '.record'))
        # registered with register_condition by demoapp
        self.assertTrue(is_allowed('demoapp.expense_both_approved'))

    def test_publishing_refuses_what_is_not_allowed(self):
        cases = {
            'transitions[0].actions[0].props.function': call(HERE + '.record'),
            'transitions[0].condition': {'condition': HERE + '.yes'},
            'transitions[0].form': {'form': HERE + '.NoteForm'},
        }
        for where, transition in cases.items():
            doc = document(**transition)
            self.assertEqual(len(validate_callables(doc)), 1, where)
            self.assertEqual(validate_callables(doc)[0].path, '$.' + where)
            with self.assertRaisesMessage(ImproperlyConfigured, where):
                publish_definition(doc)
        doc = document(condition={'function': HERE + '.yes'})
        self.assertEqual(validate_callables(doc)[0].path, '$.transitions[0].condition')
        self.assertFalse(FlowDefinition.objects.exists())

    def test_publishing_checks_states_and_cases_too(self):
        doc = document()
        doc['states'][0] = {'id': 'a', 'on_enter': call('os.system')['actions']}
        doc['states'].append({'id': 's', 'type': 'switch', 'default': 'b',
                              'cases': [{'condition': 'os.getcwd', 'target': 'b'}]})
        doc['deadlines'] = {'a': {'after': 60, **call('os.remove')}}
        doc['on_exit'] = {'a': call('os.kill')['actions']}
        errors = validate_callables(doc)
        self.assertEqual(len(errors), 4, errors)
        for path in ('os.system', 'os.getcwd', 'os.remove', 'os.kill'):
            self.assertTrue(any(path in error.message for error in errors), path)

    def test_registered_names_and_c6_conditions_are_fine(self):
        doc = document(condition={'perm': 'demoapp.view_country'})
        doc['states'].append({'id': 's', 'type': 'switch', 'default': 'b', 'cases': [
            {'condition': {'function': 'demoapp.expense_both_approved'},
             'target': 'b'}]})
        self.assertEqual(validate_callables(doc), [])

    @override_settings(GT_FLOWS_ALLOWED_CALLABLES=[HERE])
    def test_allowed_callables_publish_and_run(self):
        publish_definition(document(condition=HERE + '.yes', form=HERE + '.NoteForm',
                                    **call(HERE + '.record')))
        flow = get_flow('tests.allowlist.allowlist')
        self.assertIs(flow.get_transition('go').form, NoteForm)
        self.assertEqual(flow.run(self.country, 'go', self.root).state, 'b')
        self.assertEqual(CALLS, [self.country.pk])

    def test_a_stored_call_that_is_not_allowed_fails_audited(self):
        store(document(**call(HERE + '.record')))
        flow = get_flow('tests.allowlist.allowlist')
        with self.assertLogs('djgentelella.flows', 'WARNING') as logs:
            with self.assertRaises(CallableNotAllowed):
                flow.run(self.country, 'go', self.root)
        self.assertIn(HERE + '.record', logs.output[0])
        self.assertEqual(CALLS, [])
        self.assertEqual(flow.state(self.country), 'a')

    def test_a_stored_call_in_an_activity_leaves_it_in_error(self):
        doc = document()
        doc['states'].insert(1, {'id': 'act', 'type': 'action', 'next': 'b',
                                 **call(HERE + '.record')})
        doc['transitions'][0]['target'] = 'act'
        store(doc)
        flow = get_flow('tests.allowlist.allowlist')
        with self.assertLogs('djgentelella.flows', 'WARNING'):
            instance = flow.run(self.country, 'go', self.root)
        self.assertEqual((instance.state, instance.status), ('act', 'error'))
        self.assertIn('not an allowed callable', instance.error)
        self.assertTrue(FlowTransitionLog.objects.filter(
            instance=instance, kind='error').exists())
        self.assertEqual(CALLS, [])

    def test_a_stored_condition_that_is_not_allowed_blocks(self):
        store(document(condition=HERE + '.yes'))
        flow = get_flow('tests.allowlist.allowlist')
        with self.assertLogs('djgentelella.flows', 'WARNING'):
            ok, reason = flow.check(flow.get_transition('go'), self.country,
                                    self.root)
        self.assertFalse(ok)
        self.assertIn('not an allowed callable', str(reason))

    def test_a_stored_form_that_is_not_allowed_blocks(self):
        store(document(form=HERE + '.NoteForm'))
        flow = get_flow('tests.allowlist.allowlist')
        self.assertIsNone(flow.get_transition('go').form)
        with self.assertLogs('djgentelella.flows', 'WARNING'):
            ok, _reason = flow.check(flow.get_transition('go'), self.country,
                                     self.root)
        self.assertFalse(ok)

    def test_build_flow_still_loads_a_stored_document(self):
        flow = build_flow(document(condition=HERE + '.yes', **call('os.system')))
        self.assertEqual(str(flow.get_transition('go').condition), HERE + '.yes')

    def test_python_flows_are_not_restricted(self):
        class PythonFlow(Flow):
            name = 'tests.allowlist.python'
            model = Country
            initial = 'a'
            states = [('a', 'A'), ('b', 'B')]
            transitions = [Transition('go', 'a', 'b', condition=HERE + '.yes',
                                      actions=[CallFunction(HERE + '.record')])]

        flow = PythonFlow()
        self.assertEqual(flow.run(self.country, 'go', self.root).state, 'b')
        self.assertEqual(CALLS, [self.country.pk])

    def test_action_from_json_guards_a_call_by_itself(self):
        """Whoever builds a JSON action without guard_action still gets the
        allowlist when it runs."""
        action = action_from_json({'action': 'call',
                                   'props': {'function': HERE + '.record'}})
        context = ActionContext(obj=self.country, user=self.root)
        with self.assertLogs('djgentelella.flows', 'WARNING') as logs:
            with self.assertRaises(CallableNotAllowed):
                action.run(context)
        self.assertIn('call action', logs.output[0])
        self.assertEqual(CALLS, [])
        with override_settings(GT_FLOWS_ALLOWED_CALLABLES=[HERE + '.record']):
            action.run(context)
        self.assertEqual(CALLS, [self.country.pk])

    def test_guarding_again_names_the_new_place(self):
        action = guard_action(action_from_json(
            {'action': 'call', 'props': {'function': 'os.system'}}), 'automation 7')
        self.assertEqual((action.function.path, action.function.where),
                         ('os.system', 'automation 7'))
        with self.assertLogs('djgentelella.flows', 'WARNING') as logs:
            with self.assertRaises(CallableNotAllowed):
                action.run(ActionContext(obj=self.country, user=self.root))
        self.assertIn('automation 7', logs.output[0])
