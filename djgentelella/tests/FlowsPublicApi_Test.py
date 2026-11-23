"""The public API of djgentelella.flows for the tools built on it: actions
validated outside a document, validation errors as (path, message), the
``auto`` flag of registered flows and the types of flow variables."""

import json

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import translation
from django.utils.functional import Promise

from demoapp.models import Country
import djgentelella.flows as flows
from djgentelella.designs.jsonschema import Error
from djgentelella.flows import callables, registry, taskforms, variables
from djgentelella.flows.base import Flow, Transition, register_flow
from djgentelella.tests.FlowsAllowlist_Test import call, document

HERE = __name__
FUNCTION = HERE + '.record'
NOT_ALLOWED = ('%s is not an allowed callable (register it with register_callable '
               'or list it in GT_FLOWS_ALLOWED_CALLABLES)')


def record(context):
    """A function a ``call`` action may name."""


class PublicAutoFlow(Flow):
    name = 'tests.public.auto'
    model = Country
    states = [('a', 'A'), ('b', 'B'), ('c', 'C')]
    initial = 'a'
    transitions = [Transition('go', 'a', 'b'),
                   Transition('escalate', 'b', 'c', auto=True)]


register_flow(PublicAutoFlow)


# These tests compare messages in English: the same text whether or not
# the Spanish catalog is compiled (the demo runs in 'es').
@override_settings(LANGUAGE_CODE='en')
class ValidateActionsTests(SimpleTestCase):
    def test_a_loose_list_of_actions(self):
        specs = [{'action': 'set_field', 'props': {'field': 'name', 'value': 'x'}},
                 {'action': 'call', 'props': {'function': FUNCTION}},
                 {'action': 'call', 'props': {'function': 'os.system'}}]
        errors = callables.validate_actions(specs, '$.actions')
        self.assertEqual(errors, [
            Error('$.actions[1].props.function', NOT_ALLOWED % FUNCTION),
            Error('$.actions[2].props.function', NOT_ALLOWED % 'os.system')])
        self.assertEqual(callables.validate_actions(specs)[0].path,
                         '[1].props.function')

    @override_settings(GT_FLOWS_ALLOWED_CALLABLES=[HERE])
    def test_allowed_functions_and_other_actions_are_fine(self):
        specs = [{'action': 'call', 'props': {'function': FUNCTION}},
                 {'action': 'notify', 'props': {}}]
        self.assertEqual(callables.validate_actions(specs), [])

    def test_whatever_is_not_a_list_of_call_actions_is_ignored(self):
        self.assertEqual(callables.validate_actions(None), [])
        self.assertEqual(callables.validate_actions({'action': 'call'}), [])
        self.assertEqual(callables.validate_actions(
            ['x', {'action': 'call'}, {'action': 'call', 'props': 'x'},
             {'action': 'call', 'props': {'function': 3}}]), [])

    def test_the_document_check_uses_it(self):
        errors = callables.validate_callables(document(**call('os.system')))
        self.assertEqual(errors, [Error('$.transitions[0].actions[0].props.function',
                                        NOT_ALLOWED % 'os.system')])


# These tests compare messages in English: the same text whether or not
# the Spanish catalog is compiled (the demo runs in 'es').
@override_settings(LANGUAGE_CODE='en')
class DocumentErrorTests(TestCase):
    def test_callables_are_path_message_errors(self):
        error = callables.validate_callables(document(condition=HERE + '.record'))[0]
        self.assertIsInstance(error, Error)
        self.assertEqual(error.path, '$.transitions[0].condition')
        self.assertEqual(error.message, NOT_ALLOWED % (HERE + '.record'))
        self.assertEqual(str(error), '$.transitions[0].condition: '
                         + NOT_ALLOWED % (HERE + '.record'))

    def test_task_forms_are_path_message_errors(self):
        doc = document()
        doc['states'].append({'id': 'review', 'type': 'human_task',
                              'form': 'nowhere.Form', 'next': 'b'})
        error = taskforms.validate_task_forms(doc)[0]
        self.assertIsInstance(error, Error)
        self.assertEqual(error.path, '$.states[2].form')
        self.assertTrue(error.message.startswith('nowhere.Form is not an allowed '
                                                 'task form'))

    def test_the_text_methods_still_work(self):
        error = callables.DocumentError('$.a', 'is wrong')
        where, _colon, message = error.partition(': ')
        self.assertEqual((where, message), ('$.a', 'is wrong'))
        self.assertTrue(error.startswith('$.a'))
        self.assertIn('wrong', error)
        self.assertIn('$.a', error)
        self.assertNotIn('right', error)
        self.assertEqual(json.loads(json.dumps(error)), ['$.a', 'is wrong'])
        with self.assertRaises(AttributeError):
            error._nothing

    def test_equal_to_its_text(self):
        error = callables.DocumentError('$.a', 'is wrong')
        self.assertEqual(error, '$.a: is wrong')
        self.assertNotEqual(error, '$.a: is right')
        self.assertIn('$.a: is wrong', [error])
        self.assertEqual(error, Error('$.a', 'is wrong'))
        self.assertEqual(error, ('$.a', 'is wrong'))
        self.assertNotEqual(error, Error('$.a', 'is right'))
        # The rest is the tuple's, hash included.
        self.assertEqual(hash(error), hash(Error('$.a', 'is wrong')))
        self.assertEqual(error.index('is wrong'), 1)
        self.assertEqual(error.count('$.a'), 1)
        self.assertEqual(len(error), 2)

    def test_exported_by_the_package(self):
        self.assertIs(flows.validate_actions, callables.validate_actions)
        self.assertIs(flows.validate_callables, callables.validate_callables)
        self.assertIs(flows.is_task_form_allowed, taskforms.is_task_form_allowed)
        self.assertIs(flows.validate_task_forms, taskforms.validate_task_forms)
        self.assertIs(flows.variable_types, registry.variable_types)
        self.assertIs(flows.register_variable_type, variables.register_variable_type)
        for name in ('validate_actions', 'validate_callables', 'is_task_form_allowed',
                     'validate_task_forms', 'variable_types'):
            self.assertIn(name, flows.__all__)


class RegisteredFlowsAutoTests(SimpleTestCase):
    def test_each_transition_says_whether_it_is_automatic(self):
        found = {item['name']: item for item in registry.registered_flows()}
        entry = found['tests.public.auto']
        self.assertEqual(entry['transitions'], ['go', 'escalate'])
        self.assertEqual(entry['auto'], {'go': False, 'escalate': True})
        self.assertEqual(json.loads(json.dumps(entry)), entry)


# These tests compare messages in English: the same text whether or not
# the Spanish catalog is compiled (the demo runs in 'es').
@override_settings(LANGUAGE_CODE='en')
class VariableTypesTests(SimpleTestCase):
    def test_the_builtin_types(self):
        described = {item['name']: item for item in registry.variable_types()}
        self.assertEqual(sorted(described), sorted(
            ['string', 'integer', 'decimal', 'boolean', 'date', 'datetime', 'user',
             'list', 'object']))
        self.assertEqual(described['decimal']['json_types'], ['number', 'string'])
        self.assertEqual(described['list']['label'], 'List')
        self.assertEqual(described['datetime']['label'], 'Date and time')
        self.assertEqual([item['name'] for item in registry.variable_types()],
                         sorted(described))

    def test_the_builtin_labels_are_translatable(self):
        for kind in variables.get_variable_types().values():
            self.assertIsInstance(kind.label, Promise, kind.name)
        with translation.override('es'):
            label = variables.get_variable_type('date').label
            self.assertEqual(str(label), translation.gettext('Date'))

    def test_without_a_label_the_name_is_shown(self):
        variables.register_variable_type('code', str, json_types='string')
        self.addCleanup(variables.unregister_variable_type, 'code')
        self.assertEqual(variables.get_variable_type('code').describe()['label'],
                         'code')

    def test_values_are_checked(self):
        self.assertTrue(variables.check_variable('integer', 3))
        self.assertFalse(variables.check_variable('integer', True))
        self.assertFalse(variables.check_variable('integer', '3'))
        self.assertTrue(variables.check_variable('boolean', False))
        self.assertTrue(variables.check_variable('decimal', '2.50'))
        self.assertFalse(variables.check_variable('decimal', False))
        self.assertTrue(variables.check_variable('user', 'ana'))
        self.assertTrue(variables.check_variable('object', {}))
        self.assertFalse(variables.check_variable('list', {}))
        self.assertFalse(variables.check_variable('nothing', 'x'))

    def test_a_project_registers_its_own(self):
        variables.register_variable_type('money', (int, float, str),
                                         json_types=('number', 'string'),
                                         label='Money')
        self.addCleanup(variables.unregister_variable_type, 'money')
        self.assertIn({'name': 'money', 'label': 'Money',
                       'json_types': ['number', 'string']}, registry.variable_types())
        self.assertTrue(variables.check_variable('money', 9.5))
        self.assertEqual(variables.get_variable_type('money').python_types,
                         (int, float, str))
        variables.register_variable_type('code', str, json_types='string')
        self.addCleanup(variables.unregister_variable_type, 'code')
        self.assertEqual(variables.get_variable_type('code').json_types, ('string',))
        with self.assertRaises(ValueError):
            variables.register_variable_type('', str, json_types='string')
