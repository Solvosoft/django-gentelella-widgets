"""The form of a ``human_task`` goes through the allowlist of JSON flows."""
import json

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from demoapp.models import Country
from djgentelella.flows import get_flow, publish_definition, register_task_form
from djgentelella.flows.definitions import build_flow
from djgentelella.flows.models import FlowDefinition, FlowTransitionLog, Task
from djgentelella.flows.taskforms import (
    get_task_form,
    is_task_form_allowed,
    unregister_task_form,
    validate_task_forms,
)

HERE = __name__
NAME = 'tests.int4.taskform'


class TaskNoteForm(forms.Form):
    note = forms.CharField()


def not_a_form(context):
    return True


def document(form):
    return {
        'schema_version': 2, 'name': NAME, 'model': 'demoapp.Country',
        'initial': 'draft',
        'states': [
            {'id': 'draft'},
            {'id': 'review', 'type': 'human_task', 'title': 'Review {{ object }}',
             'groups': ['Int4 reviewers'], 'form': form,
             'outcomes': {'approve': 'done', 'reject': 'draft'}},
            {'id': 'done'},
        ],
        'transitions': [{'name': 'submit', 'source': 'draft', 'target': 'review'}],
    }


def store(doc):
    """A definition stored without publishing (an old row, a bulk load)."""
    return FlowDefinition.objects.create(name=doc['name'], version=1,
                                         document=doc, is_active=True)


class TaskFormAllowlistTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reviewers = Group.objects.create(name='Int4 reviewers')
        cls.root = get_user_model().objects.create_superuser('int4root',
                                                             password='x')
        cls.root.groups.add(cls.reviewers)

    def setUp(self):
        self.enterContext(translation.override('en'))
        self.country = Country.objects.create(name='Int4')

    def submit(self):
        return get_flow(NAME).run(self.country, 'submit', self.root)

    def test_a_path_that_is_not_allowed_is_an_error_when_publishing(self):
        doc = document(HERE + '.TaskNoteForm')
        self.assertFalse(is_task_form_allowed(HERE + '.TaskNoteForm'))
        errors = validate_task_forms(doc)
        self.assertEqual(len(errors), 1, errors)
        self.assertEqual(errors[0].path, '$.states[1].form')
        with self.assertRaisesMessage(ImproperlyConfigured, '$.states[1].form'):
            publish_definition(doc)
        self.assertFalse(FlowDefinition.objects.filter(name=NAME).exists())
        with self.assertRaises(ImproperlyConfigured):
            get_task_form(HERE + '.TaskNoteForm')

    def test_a_stored_path_that_is_not_allowed_fails_audited_when_it_runs(self):
        store(document(HERE + '.TaskNoteForm'))
        self.assertIsNone(build_flow(document(HERE + '.TaskNoteForm'))
                          .activities['review'].form)
        with self.assertLogs('djgentelella.flows', 'WARNING') as logs:
            instance = self.submit()
        self.assertIn(HERE + '.TaskNoteForm', logs.output[0])
        self.assertEqual((instance.state, instance.status), ('review', 'error'))
        self.assertIn('not an allowed callable', instance.error)
        self.assertTrue(FlowTransitionLog.objects.filter(
            instance=instance, kind='error').exists())
        self.assertFalse(Task.objects.filter(object_id=str(self.country.pk))
                         .exists())

    def test_a_stored_path_allowed_later_needs_no_new_version(self):
        store(document(HERE + '.TaskNoteForm'))
        with override_settings(GT_FLOWS_ALLOWED_CALLABLES=[HERE]):
            instance = self.submit()
        self.assertEqual((instance.state, instance.status), ('review', 'running'))
        self.assertIs(get_flow(NAME).activities['review'].form, TaskNoteForm)

    @override_settings(GT_FLOWS_ALLOWED_CALLABLES=[HERE + '.TaskNoteForm'])
    def test_an_allowed_path_publishes_and_runs(self):
        publish_definition(document(HERE + '.TaskNoteForm'))
        self.assertIs(get_flow(NAME).activities['review'].form, TaskNoteForm)
        self.submit()
        task = Task.objects.get(object_id=str(self.country.pk), state__in=Task.OPEN)
        self.client.force_login(self.root)
        page = self.client.get(reverse('task_detail', args=[task.pk]))
        self.assertContains(page, 'name="task-note"')

    @override_settings(GT_FLOWS_ALLOWED_CALLABLES=[HERE])
    def test_an_allowed_path_that_is_not_a_form_is_refused(self):
        errors = validate_task_forms(document(HERE + '.not_a_form'))
        self.assertEqual(len(errors), 1, errors)
        self.assertIn('is not a form class', errors[0].message)
        with self.assertRaises(ImproperlyConfigured):
            publish_definition(document(HERE + '.not_a_form'))

    def test_a_registered_name_works_without_the_allowlist(self):
        register_task_form('tests.int4.note')(TaskNoteForm)
        self.addCleanup(unregister_task_form, 'tests.int4.note')
        self.assertTrue(is_task_form_allowed('tests.int4.note'))
        self.assertEqual(validate_task_forms(document('tests.int4.note')), [])
        publish_definition(json.loads(json.dumps(document('tests.int4.note'))))
        instance = self.submit()
        self.assertEqual(instance.status, 'running')
        task = Task.objects.get(object_id=str(self.country.pk), state__in=Task.OPEN)
        self.client.force_login(self.root)
        response = self.client.post(
            reverse('task_action', args=[task.pk, 'complete']),
            {'outcome': 'approve', 'task-note': 'fine'})
        self.assertEqual(response.status_code, 302)
        instance.refresh_from_db()
        self.assertEqual(instance.state, 'done')
        self.assertEqual(instance.variables['note'], 'fine')
