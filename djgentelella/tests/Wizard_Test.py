"""djgentelella.wizard (GTWizardView, drafts) and the ``wizard`` design
component. Classes prefixed ``Wiz`` so the ``import *`` of
``tests/__init__.py`` never hides another module's."""

import json
from datetime import date, timedelta
from io import StringIO
from pathlib import Path

from django import forms
from django.contrib.auth.models import AnonymousUser, User
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.db import transaction
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import include, path, reverse
from django.utils import timezone

import demoapp
from demoapp.models import Department, NewHire
from demoapp.wizard.forms import JobForm, PersonalForm, VehicleForm
from demoapp.wizard.views import EmployeeWizard
from djgentelella.chunked_upload.constants import COMPLETE
from djgentelella.chunked_upload.utils import get_expired_uploads
from djgentelella.designs import engine, publishing, registry
from djgentelella.designs.exposure import expose
from djgentelella.designs.wizard import WizardComponent, when_holds
from djgentelella.models import ChunkedUpload, WizardDraft
from djgentelella.tests.Designs_Test import DesignState, design, node
from djgentelella.tests.DesignsPages_Test import grant
from djgentelella.widgets.files import FileChunkedUpload
from djgentelella.wizard import GTWizardView, Step
from djgentelella.wizard.storage import SESSION_KEY

__all__ = ['WizNavigationTests', 'WizDraftTests', 'WizUploadTests',
           'WizComponentResolveTests', 'WizComponentTests', 'WizHelpersTests']

FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']


def has_car(wizard):
    return wizard.cleaned_value('personal', 'has_car')


class SessionWizard(GTWizardView):
    """The demo wizard with session drafts, for anyone."""

    title = 'Hire'
    model = NewHire
    draft_storage = 'session'
    success_url = '/wizard-done/'
    steps = [Step('personal', PersonalForm, 'Personal data'),
             Step('vehicle', VehicleForm, 'Vehicle', condition=has_car),
             Step('job', JobForm, 'Job')]


class FailingWizard(SessionWizard):
    """Saves the object and then fails: nothing must stay."""

    wizard_key = 'tests.failing'

    def done(self, forms):
        super().done(forms)
        raise RuntimeError('boom')


class HookedWizard(SessionWizard):
    """Refuses "Bob" in ``on_step`` and records ``on_finish``."""

    wizard_key = 'tests.hooked'
    log = []

    def on_step(self, step, form):
        if step.name == 'personal' and form.cleaned_data['name'] == 'Bob':
            form.add_error('name', 'No Bobs.')

    def on_finish(self, forms, result):
        in_atomic = transaction.get_connection().in_atomic_block
        type(self).log.append((list(forms), in_atomic, self.object.pk))


class EditWizard(SessionWizard):
    """Edits the NewHire of the URL, with the optimistic lock."""

    optimistic_lock = True
    wizard_key = 'tests.edit'

    def get_object(self):
        return NewHire.objects.get(pk=self.kwargs['pk'])


class PermWizard(SessionWizard):
    """A step shown only to who holds a permission (a condition of
    djgentelella.authorization)."""

    wizard_key = 'tests.perm'
    steps = [Step('personal', PersonalForm),
             Step('vehicle', VehicleForm, condition={'perm': 'demoapp.change_newhire'}),
             Step('job', JobForm)]


def done_view(request):
    return HttpResponse('done')


urlpatterns = [
    path('wizard-test/', SessionWizard.as_view(), name='wiz_session'),
    path('wizard-failing/', FailingWizard.as_view(), name='wiz_failing'),
    path('wizard-hooked/', HookedWizard.as_view(), name='wiz_hooked'),
    path('wizard-edit/<int:pk>/', EditWizard.as_view(), name='wiz_edit'),
    path('wizard-perm/', PermWizard.as_view(), name='wiz_perm'),
    path('wizard-done/', done_view),
    path('', include('demo.urls')),
]

PERSONAL = {'wizard_step': 'personal', 'personal-name': 'Ana',
            'personal-email': 'ana@example.com', 'personal-birth_date': ''}
JOB = {'wizard_step': 'job', 'job-department': '', 'job-start_date': '2026-12-01'}


def personal(**data):
    return {**PERSONAL, **{'personal-' + key: value for key, value in data.items()}}


def state_of(client, key_part):
    everything = client.session.get(SESSION_KEY) or {}
    return next((value for key, value in everything.items() if key_part in key),
                None)


class WizBase(TestCase):
    def setUp(self):
        super().setUp()
        Site.objects.clear_cache()
        self.user = User.objects.create_user('ana', password='pw')
        self.client.force_login(self.user)

    def post(self, url, data, action='next', **extra):
        return self.client.post(url, {**data, 'wizard_action': action}, **extra)


@override_settings(ROOT_URLCONF=__name__, LANGUAGE_CODE='en',
                   PASSWORD_HASHERS=FAST_HASHERS)
class WizNavigationTests(WizBase):
    url = '/wizard-test/'

    def test_the_first_step_and_the_progress(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Step 1 of 2: Personal data')
        self.assertContains(response, 'name="personal-name"')
        self.assertContains(response, 'role="progressbar"')
        self.assertContains(response, 'aria-valuenow="1"')
        # Moving needs no javascript: a form that posts to the page.
        self.assertContains(response, '<form method="post" action="/wizard-test/"')
        self.assertContains(response, 'value="next"')
        self.assertNotContains(response, 'value="previous"')

    def test_forward_and_back_keep_the_data(self):
        response = self.post(self.url, personal())
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        response = self.client.get(self.url)
        self.assertContains(response, 'Step 2 of 2: Job')
        # Typed in the job step, then back: nothing is lost.
        self.post(self.url, {**JOB, 'job-start_date': '2026-12-24'}, 'previous')
        response = self.client.get(self.url)
        self.assertContains(response, 'Step 1 of 2')
        self.assertContains(response, 'value="Ana"')
        self.assertContains(response, 'value="ana@example.com"')
        self.post(self.url, personal())
        response = self.client.get(self.url)
        self.assertContains(response, 'Step 2 of 2')
        self.assertContains(response, '2026-12-24')

    def test_a_step_with_errors_stays(self):
        response = self.post(self.url, personal(email='not an email'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Step 1 of 2')
        self.assertContains(response, 'Please correct the errors below.')
        self.assertContains(response, 'Enter a valid email address.')
        self.assertEqual(state_of(self.client, 'SessionWizard')['current'], 'personal')
        self.assertEqual(state_of(self.client, 'SessionWizard')['valid'], [])

    def test_a_conditional_step(self):
        self.post(self.url, personal(has_car='on'))
        response = self.client.get(self.url)
        self.assertContains(response, 'Step 2 of 3: Vehicle')
        response = self.post(self.url, {'wizard_step': 'vehicle',
                                        'vehicle-car_plate': ' '})
        self.assertContains(response, 'This field is required.')
        self.post(self.url, {'wizard_step': 'vehicle', 'vehicle-car_plate': 'abc123'})
        self.assertContains(self.client.get(self.url), 'Step 3 of 3: Job')
        # Back to the first step: without a car, the vehicle step goes away
        # and its data is not saved.
        self.post(self.url, personal(), 'goto:personal')
        self.post(self.url, personal())
        self.assertContains(self.client.get(self.url), 'Step 2 of 2: Job')
        response = self.post(self.url, JOB, 'finish')
        self.assertRedirects(response, '/wizard-done/', fetch_redirect_response=False)
        hire = NewHire.objects.get()
        self.assertEqual((hire.name, hire.has_car, hire.car_plate),
                         ('Ana', False, ''))

    def test_finish_saves_one_object_and_forgets_the_state(self):
        department = Department.objects.create(name='Sales')
        self.post(self.url, personal(has_car='on'))
        self.post(self.url, {'wizard_step': 'vehicle', 'vehicle-car_plate': 'xyz9'})
        response = self.post(self.url, {**JOB, 'job-department': department.pk},
                             'finish')
        self.assertRedirects(response, '/wizard-done/', fetch_redirect_response=False)
        hire = NewHire.objects.get()
        self.assertEqual((hire.name, hire.email, hire.car_plate, hire.department,
                          hire.start_date),
                         ('Ana', 'ana@example.com', 'XYZ9', department,
                          date(2026, 12, 1)))
        self.assertIsNone(state_of(self.client, 'SessionWizard'))
        self.assertContains(self.client.get(self.url), 'Step 1 of 2')

    def test_finish_validates_every_step_again(self):
        department = Department.objects.create(name='Gone')
        gone = department.pk
        self.post(self.url, personal())
        self.post(self.url, {**JOB, 'job-department': gone}, 'previous')
        self.post(self.url, personal())
        department.delete()
        response = self.post(self.url, {**JOB, 'job-department': gone}, 'finish')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select a valid choice.')
        self.assertFalse(NewHire.objects.exists())

    def test_finish_on_the_last_step_only_after_the_others(self):
        # Posting "finish" for the last step with the first one never done:
        # it is the first step that is shown, with its errors.
        response = self.post(self.url, JOB, 'finish')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Step 1 of 2')
        self.assertFalse(NewHire.objects.exists())

    def test_goto_cannot_skip_ahead(self):
        self.post(self.url, personal(), 'goto:job')
        self.assertContains(self.client.get(self.url), 'Step 1 of 2')

    def test_done_is_atomic(self):
        self.post('/wizard-failing/', personal())
        with self.assertRaises(RuntimeError):
            self.post('/wizard-failing/', JOB, 'finish')
        self.assertFalse(NewHire.objects.exists())
        # The state is still there: the user can try again.
        state = state_of(self.client, 'tests.failing')
        self.assertEqual(state['valid'], ['personal'])
        self.assertEqual(state['data']['personal']['personal-name'], ['Ana'])

    def test_the_hooks(self):
        HookedWizard.log = []
        response = self.post('/wizard-hooked/', personal(name='Bob'))
        self.assertContains(response, 'No Bobs.')
        self.post('/wizard-hooked/', personal())
        self.post('/wizard-hooked/', JOB, 'finish')
        names, in_atomic, pk = HookedWizard.log[0]
        self.assertEqual(names, ['personal', 'job'])
        self.assertTrue(in_atomic)
        self.assertEqual(pk, NewHire.objects.get().pk)

    def test_a_step_with_a_permission_condition(self):
        self.assertContains(self.client.get('/wizard-perm/'), 'Step 1 of 2')
        self.user = grant(self.user, 'demoapp.change_newhire')
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/wizard-perm/'), 'Step 1 of 3')

    def test_discard(self):
        self.post(self.url, personal())
        self.post(self.url, {}, 'discard')
        self.assertIsNone(state_of(self.client, 'SessionWizard'))
        self.assertContains(self.client.get(self.url), 'Step 1 of 2')

    def test_optimistic_lock(self):
        hire = NewHire.objects.create(name='Old', email='old@example.com',
                                      start_date=date(2026, 1, 1))
        url = '/wizard-edit/%d/' % hire.pk
        response = self.client.get(url)
        self.assertContains(response, 'value="Old"')
        self.post(url, personal())
        # Somebody else saves it meanwhile.
        NewHire.objects.filter(pk=hire.pk).update(
            name='Changed', updated_at=timezone.now() + timedelta(seconds=5))
        response = self.post(url, JOB, 'finish')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'changed')
        hire.refresh_from_db()
        self.assertEqual(hire.name, 'Changed')
        # Discarded and started again, it saves.
        self.post(url, {}, 'discard')
        self.client.get(url)
        self.post(url, personal())
        response = self.post(url, JOB, 'finish')
        self.assertEqual(response.status_code, 302)
        hire.refresh_from_db()
        self.assertEqual(hire.name, 'Ana')
        self.assertEqual(NewHire.objects.count(), 1)


@override_settings(ROOT_URLCONF=__name__, LANGUAGE_CODE='en', ALLOWED_HOSTS=['*'],
                   PASSWORD_HASHERS=FAST_HASHERS)
class WizDraftTests(WizBase):
    url = '/wizard/employee/'

    def test_session_draft_saved_and_resumed(self):
        self.post('/wizard-test/', personal())
        response = self.post('/wizard-test/', {**JOB, 'job-start_date': 'bad'},
                             'save')
        self.assertRedirects(response, '/wizard-test/', fetch_redirect_response=False)
        response = self.client.get('/wizard-test/')
        self.assertContains(response, 'Draft saved in this session.')
        self.assertContains(response, 'Step 2 of 2')
        # Kept as typed, not refused: no errors until it is sent.
        self.assertContains(response, 'value="bad"')
        self.assertNotContains(response, 'Enter a valid date.')
        self.assertFalse(WizardDraft.objects.exists())

    def test_session_draft_expires(self):
        self.post('/wizard-test/', personal())
        with override_settings(GT_WIZARD_DRAFT_EXPIRATION=timedelta(seconds=-1)):
            self.assertContains(self.client.get('/wizard-test/'), 'Step 1 of 2')
        self.assertIsNone(state_of(self.client, 'SessionWizard'))

    def test_model_draft_saved_and_resumed_in_another_session(self):
        self.post(self.url, personal(has_car='on'))
        response = self.post(self.url, {'wizard_step': 'vehicle',
                                        'vehicle-car_plate': 'PL4TE'}, 'save')
        draft = WizardDraft.objects.get()
        self.assertEqual((draft.user, draft.site_id, draft.key),
                         (self.user, None, 'demoapp.wizard.views.EmployeeWizard'))
        self.assertEqual(draft.data['current'], 'vehicle')
        self.assertRedirects(response, '%s?draft=%s' % (self.url, draft.pk),
                             fetch_redirect_response=False)
        # Another browser of the same user.
        other = Client()
        other.force_login(self.user)
        page = other.get(self.url)
        self.assertContains(page, 'Your drafts')
        self.assertContains(page, '?draft=%s' % draft.pk)
        response = other.get(self.url, {'draft': draft.pk})
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        page = other.get(self.url)
        self.assertContains(page, 'Step 2 of 3: Vehicle')
        self.assertContains(page, 'value="PL4TE"')
        other.post(self.url, {'wizard_step': 'vehicle', 'vehicle-car_plate': 'PL4TE',
                              'wizard_action': 'next'})
        response = other.post(self.url, {**JOB, 'wizard_action': 'finish'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(NewHire.objects.get().car_plate, 'PL4TE')
        # Finished: the draft is gone.
        self.assertFalse(WizardDraft.objects.exists())

    def test_another_user_does_not_see_the_draft(self):
        self.post(self.url, personal(), 'save')
        draft = WizardDraft.objects.get()
        beto = User.objects.create_user('beto', password='pw')
        self.client.force_login(beto)
        self.assertEqual(self.client.get(self.url, {'draft': draft.pk}).status_code,
                         404)
        page = self.client.get(self.url)
        self.assertNotContains(page, str(draft.pk))
        self.assertNotContains(page, 'value="Ana"')
        # Not even by posting its id as the state's draft: a new one is made.
        self.post(self.url, personal(name='Beto'), 'save')
        draft.refresh_from_db()
        self.assertEqual(draft.data['data']['personal']['personal-name'], ['Ana'])

    def test_another_site_does_not_see_the_draft(self):
        Site.objects.create(domain='a.example', name='A')
        Site.objects.create(domain='b.example', name='B')
        self.post(self.url, personal(), 'save', HTTP_HOST='a.example')
        draft = WizardDraft.objects.get()
        self.assertEqual(draft.site.domain, 'a.example')
        response = self.client.get(self.url, {'draft': draft.pk},
                                   HTTP_HOST='b.example')
        self.assertEqual(response.status_code, 404)
        response = self.client.get(self.url, {'draft': draft.pk},
                                   HTTP_HOST='a.example')
        self.assertEqual(response.status_code, 302)

    def test_a_bad_draft_id_is_404(self):
        for value in ('nope', '00000000-0000-0000-0000-000000000000'):
            self.assertEqual(self.client.get(self.url, {'draft': value})
                             .status_code, 404)

    def test_expired_drafts_are_not_resumed_and_the_command_deletes_them(self):
        self.post(self.url, personal(), 'save')
        old = WizardDraft.objects.get()
        WizardDraft.objects.filter(pk=old.pk).update(
            updated_at=timezone.now() - timedelta(days=31))
        self.client.post(self.url, {'wizard_action': 'discard'})
        self.post(self.url, personal(name='New'), 'save')
        self.assertEqual(self.client.get(self.url, {'draft': old.pk}).status_code,
                         404)
        self.assertNotContains(self.client.get(self.url), str(old.pk))
        out = StringIO()
        call_command('delete_expired_wizard_drafts', '--dry-run', stdout=out)
        self.assertIn('1 expired wizard drafts would be deleted', out.getvalue())
        self.assertEqual(WizardDraft.objects.count(), 2)
        call_command('delete_expired_wizard_drafts', stdout=StringIO())
        self.assertEqual(list(WizardDraft.objects.values_list('data__data__personal'
                                                              '__personal-name',
                                                              flat=True)),
                         [['New']])
        with override_settings(GT_WIZARD_DRAFT_EXPIRATION=0):
            self.assertEqual(WizardDraft.objects.live().count(), 0)

    def test_anonymous_model_drafts_stay_in_the_session(self):
        view = EmployeeWizard()
        view.request = RequestFactory().get('/')
        view.request.user = AnonymousUser()
        self.assertFalse(view.uses_model_drafts())
        self.client.logout()
        self.post('/wizard-test/', personal(), 'save')
        self.assertFalse(WizardDraft.objects.exists())


def make_upload(user, name='contract.pdf', content=b'%PDF-1.4 contract'):
    upload = ChunkedUpload(user=user, filename=name, status=COMPLETE,
                           offset=len(content))
    upload.file.save(name, ContentFile(content), save=False)
    upload.save()
    return upload


@override_settings(ROOT_URLCONF=__name__, LANGUAGE_CODE='en',
                   PASSWORD_HASHERS=FAST_HASHERS)
class WizUploadTests(WizBase):
    url = '/wizard/employee/'

    def job(self, upload=None, token=None):
        value = json.dumps({'token': token or upload.upload_id}) \
            if (upload or token) else ''
        return {**JOB, 'job-contract': value}

    def test_the_upload_is_kept_by_the_draft_and_taken_when_it_finishes(self):
        upload = make_upload(self.user)
        self.post(self.url, personal())
        self.post(self.url, self.job(upload), 'save')
        draft = WizardDraft.objects.get()
        self.assertEqual(draft.uploads, [upload.upload_id])
        self.assertEqual(draft.data['files']['job']['contract']['name'],
                         'contract.pdf')
        # Validated twice already, still there.
        self.assertTrue(ChunkedUpload.objects.filter(pk=upload.pk).exists())
        page = self.client.get(self.url)
        self.assertContains(page, '"contract.pdf" is already uploaded')
        # Expired as an upload, but a live draft keeps it.
        ChunkedUpload.objects.filter(pk=upload.pk).update(
            created_on=timezone.now() - timedelta(days=5))
        self.assertFalse(get_expired_uploads().filter(pk=upload.pk).exists())
        # Sent again without a new file: the stored one is used.
        response = self.post(self.url, self.job(), 'finish')
        self.assertEqual(response.status_code, 302)
        hire = NewHire.objects.get()
        self.assertTrue(hire.contract.name.startswith('employees/contract'))
        with hire.contract.open('rb') as handle:
            self.assertEqual(handle.read(), b'%PDF-1.4 contract')
        self.assertFalse(ChunkedUpload.objects.filter(pk=upload.pk).exists())
        hire.contract.delete()

    def test_the_upload_of_another_user_is_ignored(self):
        beto = User.objects.create_user('beto', password='pw')
        theirs = make_upload(beto)
        self.post(self.url, personal())
        self.post(self.url, self.job(theirs), 'save')
        state = state_of(self.client, 'EmployeeWizard')
        self.assertNotIn('job', state['files'])
        self.post(self.url, self.job(theirs), 'finish')
        self.assertEqual(NewHire.objects.get().contract.name, '')
        self.assertTrue(ChunkedUpload.objects.filter(pk=theirs.pk).exists())
        theirs.delete()

    def test_a_vanished_upload_is_asked_again(self):
        upload = make_upload(self.user)
        self.post(self.url, personal())
        self.post(self.url, self.job(upload), 'save')
        draft = WizardDraft.objects.get()
        upload.delete()
        self.client.get(self.url, {'draft': draft.pk})
        state = state_of(self.client, 'EmployeeWizard')
        self.assertEqual(state['files'], {})
        self.assertNotIn('job', state['valid'])

    def test_consume_upload(self):
        upload = make_upload(self.user)
        widget = FileChunkedUpload()
        widget.consume_upload = False
        value = widget.value_from_datadict(
            {'f': json.dumps({'token': upload.upload_id})}, {}, 'f')
        self.assertEqual(value.name, 'contract.pdf')
        self.assertEqual(widget.format_value(value), '')
        self.assertTrue(ChunkedUpload.objects.filter(pk=upload.pk).exists())
        widget = FileChunkedUpload()
        widget.value_from_datadict({'f': json.dumps({'token': upload.upload_id})},
                                   {}, 'f')
        self.assertFalse(ChunkedUpload.objects.filter(pk=upload.pk).exists())


# -- the design component -------------------------------------------------------

STEPS = [
    {'name': 'personal', 'title': 'Personal data',
     'fields': ['name', 'email', 'birth_date', 'has_car']},
    {'name': 'vehicle', 'title': 'Vehicle', 'fields': ['car_plate'],
     'when': {'field': 'has_car', 'equals': True}},
    {'name': 'job', 'title': 'Job', 'fields': ['department', 'start_date']},
]


def wizard(**props):
    return node('wizard', 'hire', {'model': 'demoapp.NewHire', 'steps': STEPS,
                                   **props})


@override_settings(LANGUAGE_CODE='en')
class WizComponentResolveTests(DesignState, TestCase):
    def setUp(self):
        super().setUp()
        registry.get_components()
        expose(NewHire)
        expose(Department)

    def errors(self, *nodes, **meta):
        _resolved, errors = engine.resolve(design(*nodes, **meta))
        return [(error.path, error.message) for error in errors]

    def at(self, errors, suffix):
        return [message for where, message in errors if where.endswith(suffix)]

    def test_registered_last_with_the_editor_hints(self):
        self.assertEqual(list(registry.get_components())[-1], 'wizard')
        schema = WizardComponent.props_schema
        self.assertEqual(schema['properties']['steps']['x-widget'], 'wizard-steps')
        step = schema['properties']['steps']['items']['properties']
        self.assertEqual(step['when']['x-widget'], 'step-when')
        self.assertEqual(step['condition']['x-widget'], 'condition')
        self.assertEqual(schema['properties']['site_field']['x-filter'], 'site')

    def test_a_valid_wizard(self):
        resolved, errors = engine.resolve(design(wizard(site_field='site')))
        self.assertEqual(errors, [])
        build = resolved.nodes['hire'].build
        self.assertEqual([step.name for step in build.steps],
                         ['personal', 'vehicle', 'job'])
        self.assertEqual(build.steps[1].when['step'], 'personal')
        self.assertEqual(build.perms, {'create': ['demoapp.add_newhire'],
                                       'update': ['demoapp.change_newhire']})
        self.assertEqual(build.title, 'New %s' % NewHire._meta.verbose_name)

    def test_the_demo_designs_resolve(self):
        folder = Path(demoapp.__file__).parent / 'gtdesign'
        for name in ('employee_wizard', 'employee_edit'):
            document = json.loads((folder / ('%s.json' % name)).read_text())
            _resolved, errors = engine.resolve(document)
            self.assertEqual(errors, [], name)

    def test_errors(self):
        steps = [dict(STEPS[0]), dict(STEPS[1]), dict(STEPS[2])]
        steps[2] = {**steps[2], 'fields': ['department', 'start_date', 'name']}
        errors = self.errors(wizard(steps=steps))
        self.assertIn("'name' is already in step 'personal'",
                      self.at(errors, 'steps[2].fields'))
        missing = [dict(STEPS[0]), {**STEPS[2], 'fields': ['department']}]
        errors = self.errors(wizard(steps=missing))
        self.assertIn("'start_date' is required by demoapp.NewHire and no step asks "
                      "for it", self.at(errors, '.props.steps'))
        later = [{**STEPS[1], 'when': {'field': 'start_date', 'equals': 'x'}},
                 STEPS[0], STEPS[2]]
        errors = self.errors(wizard(steps=later))
        self.assertIn("'start_date' is not a field of an earlier step",
                      self.at(errors, 'when.field'))
        two = [STEPS[0], {**STEPS[1], 'when': {'field': 'has_car', 'equals': True,
                                               'filled': True}}, STEPS[2]]
        self.assertTrue(self.at(self.errors(wizard(steps=two)), 'steps[1].when'))
        self.assertTrue(self.at(self.errors(wizard(mode='edit')), '.props.mode'))
        self.assertTrue(self.at(self.errors(wizard(optimistic_lock=True)),
                                '.props.optimistic_lock'))
        self.assertTrue(self.at(self.errors(wizard(site_field='department')),
                                '.props.site_field'))
        self.assertTrue(self.at(self.errors(wizard(site_field='site', steps=[
            {**STEPS[0], 'fields': STEPS[0]['fields'] + ['site']}, STEPS[2]])),
            'steps[0].fields'))
        bad_condition = [STEPS[0], {**STEPS[1], 'condition': {'perm': 'nope'}},
                         STEPS[2]]
        self.assertTrue(self.at(self.errors(wizard(steps=bad_condition)),
                                'condition.perm'))
        self.assertTrue(self.at(self.errors(wizard(success_url='no-such-url')),
                                '.props.success_url'))
        file_input = [STEPS[0], {**STEPS[2], 'fields': ['start_date', 'contract'],
                                 'widgets': {'contract': 'FileInput'}}]
        self.assertTrue(self.at(self.errors(wizard(steps=file_input)),
                                'widgets.contract'))

    def test_a_file_field_is_uploaded_in_chunks(self):
        steps = [STEPS[0], {**STEPS[2], 'fields': ['start_date', 'contract']}]
        resolved, errors = engine.resolve(design(wizard(steps=steps)))
        self.assertEqual(errors, [])
        form = resolved.nodes['hire'].build.steps[1].form
        self.assertEqual(form.fields[1].widget, 'FileChunkedUpload')

    def test_edit_needs_the_page_of_its_model(self):
        errors = self.errors(wizard(mode='edit', optimistic_lock=True),
                             parent={'model': 'demoapp.NewHire'})
        self.assertEqual(errors, [])

    def test_preview(self):
        resolved, errors = engine.resolve(design(wizard()), preview=True)
        self.assertEqual(errors, [])
        html = engine.render(resolved, RequestFactory().get('/'))
        self.assertIn('Step 1 of 3: Personal data', html.content.decode())


@override_settings(LANGUAGE_CODE='en', ALLOWED_HOSTS=['*'],
                   PASSWORD_HASHERS=FAST_HASHERS)
class WizComponentTests(DesignState, TestCase):
    def setUp(self):
        super().setUp()
        registry.get_components()
        expose(NewHire)
        expose(Department)
        self.site_a = Site.objects.create(domain='a.example', name='A')
        self.site_b = Site.objects.create(domain='b.example', name='B')
        self.user = grant(User.objects.create_user('ana', password='pw'),
                          'demoapp.add_newhire', 'demoapp.change_newhire',
                          'demoapp.view_newhire')
        self.client.force_login(self.user)

    def publish(self, *nodes, path='hire', **meta):
        page, errors = publishing.publish(design(*nodes, **meta), path=path)
        self.assertEqual(errors, [])
        return page

    def endpoint(self, page, rest=''):
        return reverse('gt-design-endpoint', kwargs={
            'page_id': page.pk, 'node_id': 'hire', 'rest': rest})

    def page_url(self, page, suffix=''):
        return reverse('gt-design-page', args=[page.path + suffix])

    def post(self, url, data, action='next', host='a.example'):
        return self.client.post(url, {**data, 'wizard_action': action},
                                HTTP_HOST=host)

    def get(self, url, host='a.example', **params):
        return self.client.get(url, params, HTTP_HOST=host)

    def test_create_through_the_endpoint(self):
        page = self.publish(wizard(site_field='site'))
        response = self.get(self.page_url(page))
        self.assertContains(response, 'Step 1 of 2: Personal data')
        self.assertContains(response, 'action="%s"' % self.endpoint(page))
        response = self.post(self.endpoint(page), personal(email='bad'))
        # Errors: back to the page, which shows them once.
        self.assertRedirects(response, self.page_url(page),
                             fetch_redirect_response=False)
        response = self.get(self.page_url(page))
        self.assertContains(response, 'Enter a valid email address.')
        self.assertNotContains(self.get(self.page_url(page)),
                               'Enter a valid email address.')
        self.post(self.endpoint(page), personal(has_car='on'))
        self.assertContains(self.get(self.page_url(page)), 'Step 2 of 3: Vehicle')
        self.post(self.endpoint(page), {'wizard_step': 'vehicle',
                                        'vehicle-car_plate': 'car1'})
        response = self.post(self.endpoint(page), JOB, 'finish')
        self.assertRedirects(response, self.page_url(page),
                             fetch_redirect_response=False)
        hire = NewHire.objects.get()
        self.assertEqual((hire.name, hire.car_plate, hire.site),
                         ('Ana', 'car1', self.site_a))
        self.assertContains(self.get(self.page_url(page)), 'Saved.')

    def test_model_drafts_and_another_user(self):
        page = self.publish(wizard(draft='model'))
        self.post(self.endpoint(page), personal(), 'save')
        draft = WizardDraft.objects.get()
        self.assertEqual(draft.site, self.site_a)
        self.assertEqual(draft.key, 'gtdesign:hire:hire')
        other = Client()
        other.force_login(self.user)
        response = other.get(self.endpoint(page), {'draft': draft.pk},
                             HTTP_HOST='a.example')
        self.assertRedirects(response, self.page_url(page),
                             fetch_redirect_response=False)
        self.assertContains(other.get(self.page_url(page), HTTP_HOST='a.example'),
                            'value="Ana"')
        beto = grant(User.objects.create_user('beto', password='pw'),
                     'demoapp.add_newhire')
        self.client.force_login(beto)
        self.assertEqual(self.get(self.endpoint(page), draft=draft.pk).status_code,
                         404)
        self.assertEqual(self.get(self.endpoint(page), host='b.example',
                                  draft=draft.pk).status_code, 404)

    def test_permissions(self):
        page = self.publish(wizard())
        beto = User.objects.create_user('beto', password='pw')
        self.client.force_login(beto)
        response = self.get(self.page_url(page))
        self.assertContains(response, 'You do not have permission to see this.')
        self.assertNotContains(response, 'name="personal-name"')
        self.assertEqual(self.post(self.endpoint(page), personal()).status_code, 403)
        self.assertFalse(NewHire.objects.exists())

    def test_a_hidden_node_serves_nothing(self):
        page = self.publish(wizard(condition={'perm': 'demoapp.delete_newhire'}))
        self.assertEqual(self.post(self.endpoint(page), personal()).status_code, 404)

    def test_csrf_is_checked(self):
        page = self.publish(wizard())
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(self.endpoint(page), personal(), HTTP_HOST='a.example')
        self.assertEqual(response.status_code, 403)

    def test_edit_with_site_and_lock(self):
        page = self.publish(wizard(mode='edit', site_field='site',
                                   optimistic_lock=True),
                            path='hire-edit', parent={'model': 'demoapp.NewHire'})
        mine = NewHire.objects.create(name='Mine', email='m@example.com',
                                      start_date=date(2026, 1, 1), site=self.site_a)
        theirs = NewHire.objects.create(name='Theirs', email='t@example.com',
                                        start_date=date(2026, 1, 1),
                                        site=self.site_b)
        response = self.get(self.page_url(page, '/%d' % mine.pk))
        self.assertContains(response, 'value="Mine"')
        endpoint = self.endpoint(page, '%d/' % mine.pk)
        self.assertContains(response, 'action="%s"' % endpoint)
        # The object of another Site: nothing.
        self.assertEqual(self.post(self.endpoint(page, '%d/' % theirs.pk),
                                   personal()).status_code, 404)
        self.post(endpoint, personal(name='Renamed'))
        NewHire.objects.filter(pk=mine.pk).update(
            email='other@example.com', updated_at=timezone.now() + timedelta(1))
        response = self.post(endpoint, JOB, 'finish')
        self.assertRedirects(response, self.page_url(page, '/%d' % mine.pk),
                             fetch_redirect_response=False)
        mine.refresh_from_db()
        self.assertEqual((mine.name, mine.email), ('Mine', 'other@example.com'))
        self.assertContains(self.get(self.page_url(page, '/%d' % mine.pk)),
                            'changed')
        # Started again from the current version: saved, Site untouched.
        self.post(endpoint, {}, 'discard')
        self.get(self.page_url(page, '/%d' % mine.pk))
        self.post(endpoint, personal(name='Renamed'))
        self.post(endpoint, JOB, 'finish')
        mine.refresh_from_db()
        self.assertEqual((mine.name, mine.site), ('Renamed', self.site_a))


class WizHelpersTests(TestCase):
    def test_when_holds(self):
        department = Department(pk=4, name='x')
        self.assertTrue(when_holds({'equals': True}, True))
        self.assertFalse(when_holds({'equals': True}, False))
        self.assertTrue(when_holds({'equals': 4}, department))
        self.assertTrue(when_holds({'equals': '4'}, department))
        self.assertTrue(when_holds({'in': ['a', 'b']}, 'b'))
        self.assertTrue(when_holds({'filled': True}, 'x'))
        self.assertTrue(when_holds({'filled': False}, ''))
        self.assertTrue(when_holds({'equals': '2026-01-02'}, date(2026, 1, 2)))
        self.assertFalse(when_holds({'equals': 'True'}, False))

    def test_step_names(self):
        for bad in ('', 'a:b', 'a|b'):
            with self.assertRaises(ImproperlyConfigured):
                Step(bad, forms.Form)
