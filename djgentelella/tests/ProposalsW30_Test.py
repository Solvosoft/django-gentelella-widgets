"""W30: the page pipeline inside the wizard, ``site_field`` in the forms of a
model, the geocoder per request, metric cards without a period, facets and
metrics for generated code, and the small proposals of the 10b wave.
Classes prefixed ``W30`` so the ``import *`` of ``tests/__init__.py`` never
hides another module's."""

import json
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.test import RequestFactory, TestCase, override_settings
from django.urls import include, path, reverse
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.generic import CreateView, View
from rest_framework import serializers, viewsets
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.exceptions import ValidationError as APIValidationError

from demoapp.models import Department, NewHire, PurchaseRequest, SupportTicket
from demoapp.wizard.forms import JobForm, PersonalForm
from djgentelella import geocoding, menu
from djgentelella.authorization import authorization
from djgentelella.datasources.base import ModelDataSource
from djgentelella.designs import engine, factories, publishing, registry
from djgentelella.designs.data_components import facets_page_context
from djgentelella.designs.exposure import expose
from djgentelella.designs import pipeline as pipelines
from djgentelella.designs.components import ResolveContext
from djgentelella.designs.pipeline import (
    BranchBuild, PipelineBuild, PipelineFormMixin, PipelinePageMixin,
    PipelineViewSetMixin, build_pipeline, process, step_build,
)
from djgentelella.designs.regions import region_page_context
from djgentelella.models import MenuItem, WizardDraft
from djgentelella.serializers import GTMarkdownHTMLField
from djgentelella.tests.ChartFacets_Test import STATUS_DRAFT, chart
from djgentelella.tests.ChartFacets_Test import page as chart_page
from djgentelella.tests.Designs_Test import DesignState, design, node
from djgentelella.tests.DesignsData_Test import ALL_PRODUCT_PERMS, DataDesignTestCase
from djgentelella.tests.DesignsPages_Test import grant
from djgentelella.tests.TreeTimelineMetrics_Test import TTMBase, metrics
from djgentelella.tests.Wizard_Test import JOB, STEPS, personal, state_of
from djgentelella.widgets.geocoding import GeocodedAddressInput
from djgentelella.wizard import GTWizardView, Step

__all__ = ['W30WizardPipelineTests', 'W30WizardComponentPipelineTests',
           'W30EditorHooksTests', 'W30PipelineMixinsTests',
           'W30BuildPipelineTests', 'W30SiteFieldTests', 'W30GeocoderTests',
           'W30MetricsTests', 'W30FacetsTests', 'W30SmallTests']

FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
calls = []


# -- the steps of the pipelines ----------------------------------------------------

@process('tests_w30.no_bob', kind='validation')
def no_bob(ctx):
    if ctx.data.get('name') == 'Bob':
        ctx.add_error('name', 'No Bobs.')


@process('tests_w30.plate', kind='computation')
def plate(ctx):
    # Idempotent: the same value however often the step validates.
    calls.append('plate')
    return {'car_plate': 'AUTO-%s' % ctx.data['name'].upper()}


@process('tests_w30.not_xmas', kind='validation')
def not_xmas(ctx):
    start = ctx.data.get('start_date')
    if start is not None and (start.month, start.day) == (12, 25):
        ctx.add_error('start_date', 'Not on Christmas.')


@process('tests_w30.audit', kind='process')
def audit(ctx):
    calls.append(('audit', ctx.instance.pk, ctx.instance.car_plate))
    if ctx.instance.name == 'Fail':
        raise RuntimeError('the audit service is down')


@process('tests_w30.greet', kind='computation')
def greet(ctx):
    ctx.add_context(greeting='hello')


@process('tests_w30.deny', kind='validation')
def deny(ctx):
    if ctx.request.GET.get('deny'):
        ctx.add_error(None, 'Not today.')


@authorization('tests.w30.has_car', cache=False)
def has_car(request, obj=None):
    return bool(obj is not None and obj.has_car)


STEP_PIPELINE = {'steps': [{'name': 'tests_w30.no_bob'},
                           {'name': 'tests_w30.plate', 'writes': ['car_plate']}]}
FINISH_PIPELINE = {'steps': [{'name': 'tests_w30.audit'},
                             {'name': 'tests_w30.not_xmas'}],
                   'branches': [{'to': '/w30-car/',
                                 'condition': {'auth': 'tests.w30.has_car'}},
                                {'to': '/w30-done/'}]}


class PipelineWizard(GTWizardView):
    title = 'Hire'
    model = NewHire
    draft_storage = 'session'
    wizard_key = 'tests.w30'
    success_url = '/wizard-done/'
    steps = [Step('personal', PersonalForm, 'Personal data', pipeline=STEP_PIPELINE),
             Step('job', JobForm, 'Job')]
    pipeline = FINISH_PIPELINE


class DraftPipelineWizard(PipelineWizard):
    draft_storage = 'model'
    wizard_key = 'tests.w30.drafts'


class ProcessStepWizard(PipelineWizard):
    """A process in the pipeline of a step: refused."""

    wizard_key = 'tests.w30.bad'
    steps = [Step('personal', PersonalForm,
                  pipeline={'steps': [{'name': 'tests_w30.audit'}]}),
             Step('job', JobForm)]


urlpatterns = [
    path('w30-wizard/', PipelineWizard.as_view()),
    path('w30-drafts/', DraftPipelineWizard.as_view()),
    path('w30-bad/', ProcessStepWizard.as_view()),
    path('', include('demo.urls')),
]


def site_geocoder(request):
    """A geocoder per Site: only ``a.example`` has one."""
    site = Site.objects.filter(domain=request.get_host()).first() \
        if request is not None else None
    if site is None or site.domain != 'a.example':
        return None
    return W30Geocoder(prefix=site.name)


class W30Geocoder(geocoding.Geocoder):
    def __init__(self, prefix='X'):
        self.prefix = prefix

    def search(self, query, limit=5):
        return [geocoding.Place('%s %s' % (self.prefix, query), 9.9, -84.0)]


# -- the wizard in code ---------------------------------------------------------------

@override_settings(ROOT_URLCONF=__name__, LANGUAGE_CODE='en',
                   PASSWORD_HASHERS=FAST_HASHERS)
class W30WizardPipelineTests(TestCase):
    url = '/w30-wizard/'

    def setUp(self):
        super().setUp()
        Site.objects.clear_cache()
        calls.clear()
        self.user = User.objects.create_user('ana', password='pw')
        self.client.force_login(self.user)

    def post(self, data, action='next', url=None):
        return self.client.post(url or self.url, {**data, 'wizard_action': action})

    def test_a_validation_keeps_the_user_in_the_step(self):
        response = self.post(personal(name='Bob'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No Bobs.')
        self.assertContains(response, 'Step 1 of 2: Personal data')
        state = state_of(self.client, 'tests.w30')
        self.assertEqual((state['current'], state['valid']), ('personal', []))
        self.assertNotIn('personal', state['computed'])

    def test_the_computation_is_kept_in_the_state(self):
        self.post(personal())
        state = state_of(self.client, 'tests.w30')
        self.assertEqual(state['computed'], {'personal': {'car_plate': 'AUTO-ANA'}})
        self.assertEqual(state['current'], 'job')

    def test_the_computation_is_kept_in_the_draft(self):
        self.post(personal(), url='/w30-drafts/')
        self.post(personal(name='Eva'), 'save', url='/w30-drafts/')
        draft = WizardDraft.objects.get()
        self.assertEqual(draft.data['computed'],
                         {'personal': {'car_plate': 'AUTO-EVA'}})

    def test_finish_saves_runs_the_process_and_branches(self):
        self.post(personal())
        response = self.post(JOB, 'finish')
        self.assertRedirects(response, '/w30-done/', fetch_redirect_response=False)
        hire = NewHire.objects.get()
        # Computed in the first step, outside its form ("writes"): saved.
        self.assertEqual((hire.name, hire.car_plate), ('Ana', 'AUTO-ANA'))
        self.assertIn(('audit', hire.pk, 'AUTO-ANA'), calls)
        self.assertIsNone(state_of(self.client, 'tests.w30'))
        # The first branch that holds for the saved object wins.
        self.post(personal(name='Ceci', has_car='on'))
        response = self.post(JOB, 'finish')
        self.assertRedirects(response, '/w30-car/', fetch_redirect_response=False)

    def test_a_failing_process_rolls_everything_back(self):
        self.post(personal(name='Fail'))
        with self.assertLogs('djgentelella.designs.pipeline', 'ERROR'):
            response = self.post(JOB, 'finish')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'could not be completed: nothing was saved.')
        self.assertContains(response, 'Step 2 of 2: Job')
        self.assertFalse(NewHire.objects.exists())
        # The state stays: fixing the data and finishing again works.
        state = state_of(self.client, 'tests.w30')
        self.assertEqual(state['valid'], ['personal', 'job'])
        self.post(personal(name='Fine'), 'goto:personal')
        self.post(personal(name='Fine'))
        self.assertEqual(self.post(JOB, 'finish').status_code, 302)
        self.assertEqual(NewHire.objects.get().name, 'Fine')

    def test_a_validation_of_the_finish_stays_at_the_last_step(self):
        self.post(personal())
        response = self.post({**JOB, 'job-start_date': '2026-12-25'}, 'finish')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Not on Christmas.')
        self.assertFalse(NewHire.objects.exists())
        # A validation stops it before the save: no process ran.
        self.assertFalse([call for call in calls if call[0] == 'audit'])

    def test_a_process_in_a_step_is_refused(self):
        with self.assertRaises(ImproperlyConfigured):
            self.post(personal(), url='/w30-bad/')


@override_settings(LANGUAGE_CODE='en')
class W30BuildPipelineTests(TestCase):
    def test_a_stage_in_code(self):
        found = build_pipeline(FINISH_PIPELINE, model=NewHire)
        self.assertIsInstance(found, PipelineBuild)
        self.assertEqual([step.kind for step in found.steps],
                         ['validation', 'process'])
        self.assertEqual([branch.url for branch in found.branches],
                         ['/w30-car/', '/w30-done/'])
        self.assertIs(build_pipeline(found), found)
        self.assertIsNone(build_pipeline(None))
        self.assertIsNone(build_pipeline({}))

    def test_what_a_step_of_a_wizard_refuses(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'is a process'):
            build_pipeline({'steps': [{'name': 'tests_w30.audit'}]}, model=NewHire,
                           intermediate=True)
        with self.assertRaisesMessage(ImproperlyConfigured, 'does not branch'):
            build_pipeline({'branches': [{'to': '/x/'}]}, intermediate=True)
        with self.assertRaisesMessage(ImproperlyConfigured, 'is registered'):
            build_pipeline({'steps': [{'name': 'tests_w30.nope'}]})
        with self.assertRaises(ImproperlyConfigured):
            build_pipeline({'steps': 'not a list'})
        with self.assertRaisesMessage(ImproperlyConfigured, 'no field'):
            build_pipeline({'steps': [{'name': 'tests_w30.plate',
                                       'writes': ['nope']}]}, model=NewHire)


# -- the wizard component ----------------------------------------------------------

def wizard_node(steps=None, **props):
    return node('wizard', 'hire', {'model': 'demoapp.NewHire',
                                   'steps': steps or STEPS, **props})


def piped_steps(on_submit=None):
    steps = json.loads(json.dumps(STEPS))
    steps[0]['pipeline'] = {'on_submit': on_submit or STEP_PIPELINE}
    return steps


@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS,
                   ALLOWED_HOSTS=['*'])
class W30WizardComponentPipelineTests(DesignState, TestCase):
    def setUp(self):
        super().setUp()
        calls.clear()
        registry.get_components()
        expose(NewHire)
        expose(Department)
        self.site_a = Site.objects.create(domain='a.example', name='A')
        self.user = grant(User.objects.create_user('ana', password='pw'),
                          'demoapp.add_newhire', 'demoapp.change_newhire',
                          'demoapp.view_newhire')
        self.client.force_login(self.user)

    def errors(self, *nodes):
        _resolved, errors = engine.resolve(design(*nodes))
        return [(error.path, error.message) for error in errors]

    def publish(self, *nodes):
        page, errors = publishing.publish(design(*nodes), path='hire')
        self.assertEqual(errors, [])
        return page

    def endpoint(self, page):
        return reverse('gt-design-endpoint', kwargs={
            'page_id': page.pk, 'node_id': 'hire', 'rest': ''})

    def post(self, page, data, action='next'):
        return self.client.post(self.endpoint(page), {**data, 'wizard_action': action},
                                HTTP_HOST='a.example')

    def page_html(self):
        return self.client.get(reverse('gt-design-page', args=['hire']),
                               HTTP_HOST='a.example').content.decode()

    def test_the_schema_has_the_pipelines(self):
        component = registry.get_component('wizard')
        schema = component.props_schema['properties']
        self.assertEqual(schema['pipeline']['x-widget'], 'pipeline')
        step = schema['steps']['items']['properties']
        self.assertEqual(step['pipeline']['x-widget'], 'pipeline')

    def test_a_step_takes_no_process_and_no_branch(self):
        errors = self.errors(wizard_node(piped_steps(
            {'steps': [{'name': 'tests_w30.audit'}],
             'branches': [{'to': '/x/'}]})))
        paths = [where for where, _message in errors]
        self.assertTrue(any(where.endswith(
            'steps[0].pipeline.on_submit.steps[0].name') for where in paths), errors)
        self.assertTrue(any(where.endswith('steps[0].pipeline.on_submit.branches')
                            for where in paths), errors)
        self.assertEqual(self.errors(wizard_node(
            piped_steps(), pipeline={'on_submit': FINISH_PIPELINE})), [])

    def test_the_pipelines_through_the_endpoint(self):
        page = self.publish(wizard_node(piped_steps(), site_field='site',
                                        pipeline={'on_submit': FINISH_PIPELINE}))
        build = engine.resolve(design(wizard_node(
            piped_steps(), pipeline={'on_submit': FINISH_PIPELINE})))[0] \
            .nodes['hire'].build
        self.assertEqual([step.name for step in build.steps[0].pipeline.steps],
                         ['tests_w30.no_bob', 'tests_w30.plate'])
        self.assertEqual(len(build.pipeline.branches), 2)
        # A refused step: back to the page, which shows the error once.
        self.post(page, personal(name='Bob'))
        self.assertIn('No Bobs.', self.page_html())
        self.assertNotIn('No Bobs.', self.page_html())
        self.post(page, personal())
        response = self.post(page, JOB, 'finish')
        self.assertRedirects(response, '/w30-done/', fetch_redirect_response=False)
        hire = NewHire.objects.get()
        self.assertEqual((hire.car_plate, hire.site), ('AUTO-ANA', self.site_a))

    def test_a_failing_process_at_the_end(self):
        page = self.publish(wizard_node(piped_steps(),
                                        pipeline={'on_submit': FINISH_PIPELINE}))
        self.post(page, personal(name='Fail'))
        with self.assertLogs('djgentelella.designs.pipeline', 'ERROR'):
            response = self.post(page, JOB, 'finish')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(NewHire.objects.exists())
        html = self.page_html()
        self.assertIn('could not be completed: nothing was saved.', html)
        self.assertIn('Step 2 of 2: Job', html)


# -- site_field in object_management and crud_classic ------------------------------

UNIT_FORM = {'unit': {'model': 'demoapp.Department', 'fields': ['name', 'head']}}
UNIT_PERMS = ['demoapp.%s_department' % action
              for action in ('view', 'add', 'change', 'delete')]


@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS,
                   ALLOWED_HOSTS=['*'])
class W30SiteFieldTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        expose(Department)
        Site.objects.clear_cache()
        self.site_a = Site.objects.create(domain='a.example', name='A')
        self.site_b = Site.objects.create(domain='b.example', name='B')
        self.grant(*UNIT_PERMS)
        self.mine = Department.objects.create(name='Mine', site=self.site_a)
        self.theirs = Department.objects.create(name='Theirs', site=self.site_b)
        self.shared = Department.objects.create(name='Shared')

    def get(self, url, **params):
        return self.client.get(url, params, HTTP_HOST='a.example')

    def table(self, **props):
        return design(node('object_management', 'units', {
            'model': 'demoapp.Department', 'form': 'unit', 'site_field': 'site',
            **props}), node('facets', 'f', {'target': 'units', 'columns': ['head']}),
            forms=UNIT_FORM)

    def test_what_resolve_checks(self):
        errors = ' '.join(self.errors(self.table(site_field='name')))
        self.assertIn("'name' is not a foreign key of demoapp.Department to "
                      "sites.Site", errors)
        expose(Site)
        asks_for_it = design(node('object_management', 'units', {
            'model': 'demoapp.Department', 'form': 'unit', 'site_field': 'site'}),
            forms={'unit': {'model': 'demoapp.Department',
                            'fields': ['name', 'site']}})
        self.assertIn("'site' is the site_field", ' '.join(self.errors(asks_for_it)))
        self.assertIn("'name' is not a foreign key", ' '.join(self.errors(design(
            node('crud_classic', 'units', {'model': 'demoapp.Department',
                                           'site_field': 'name'})))))
        resolved, errors = engine.resolve(design(node('crud_classic', 'units', {
            'model': 'demoapp.Department', 'site_field': 'site'})))
        self.assertEqual(errors, [])
        build = resolved.nodes['units'].build
        self.assertEqual(build.site_field, 'site')
        # The default form leaves out the field the component sets.
        self.assertNotIn('site', build.form.field_names)

    def test_object_management_rows_of_the_site(self):
        page = self.publish(self.table(), path='units')
        url = self.api(page, 'units')
        names = sorted(row['name'] for row in self.get(url).json()['data'])
        self.assertEqual(names, ['Mine', 'Shared'])
        self.assertEqual(self.get(url + '%d/' % self.theirs.pk).status_code, 404)
        self.assertEqual(self.get(url + '%d/' % self.mine.pk).status_code, 200)
        response = self.client.put(url + '%d/' % self.theirs.pk,
                                   json.dumps({'name': 'Mine now', 'head': ''}),
                                   content_type='application/json',
                                   HTTP_HOST='a.example')
        self.assertEqual(response.status_code, 404)
        self.theirs.refresh_from_db()
        self.assertEqual(self.theirs.name, 'Theirs')
        response = self.client.post(url, json.dumps({'name': 'New', 'head': 'Eva'}),
                                    content_type='application/json',
                                    HTTP_HOST='a.example')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Department.objects.get(name='New').site, self.site_a)
        # The facets of its panel count the same rows.
        facets = self.get(self.api(page, 'f') + 'facets/',
                          params=json.dumps({})).json()
        self.assertEqual(sum(item['count'] for item in facets['head']), 3)

    def test_crud_classic_pages_of_the_site(self):
        page = self.publish(design(node('crud_classic', 'units', {
            'model': 'demoapp.Department', 'form': 'unit', 'site_field': 'site'}),
            forms=UNIT_FORM), path='crud-units')
        base = self.api(page, 'units')
        content = self.get(base).content.decode()
        self.assertIn('Mine', content)
        self.assertIn('Shared', content)
        self.assertNotIn('Theirs', content)
        for rest in ('%d/', '%d/update/', '%d/delete/'):
            self.assertEqual(self.get(base + rest % self.theirs.pk).status_code, 404)
        self.assertEqual(self.get(base + '%d/' % self.mine.pk).status_code, 200)
        response = self.client.post(base + 'create/', {'name': 'Created', 'head': ''},
                                    HTTP_HOST='a.example')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Department.objects.get(name='Created').site, self.site_a)
        response = self.client.post(base + '%d/update/' % self.theirs.pk,
                                    {'name': 'Taken', 'head': ''},
                                    HTTP_HOST='a.example')
        self.assertEqual(response.status_code, 404)

    def test_without_it_nothing_changes(self):
        page = self.publish(self.table(site_field=''), path='all-units')
        names = sorted(row['name'] for row in
                       self.get(self.api(page, 'units')).json()['data'])
        self.assertEqual(names, ['Mine', 'Shared', 'Theirs'])


# -- the geocoder per request ------------------------------------------------------

@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS,
                   ALLOWED_HOSTS=['*'])
class W30GeocoderTests(TestCase):
    def setUp(self):
        super().setUp()
        Site.objects.clear_cache()
        Site.objects.create(domain='a.example', name='A')
        Site.objects.create(domain='b.example', name='B')
        self.user = User.objects.create_user('geo', password='x')
        self.client.force_login(self.user)
        self.url = reverse('gt-geocode')

    def search(self, host):
        return self.client.get(self.url, {'q': 'Centro'}, HTTP_HOST=host)

    @override_settings(GT_GEOCODER='djgentelella.tests.ProposalsW30_Test.site_geocoder')
    def test_a_function_of_the_request(self):
        response = self.search('a.example')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'][0]['label'], 'A Centro')
        # No geocoder for that Site: as if there were none.
        self.assertEqual(self.search('b.example').status_code, 404)
        self.assertTrue(geocoding.geocoder_configured())
        self.assertIsNone(geocoding.get_geocoder())
        request = RequestFactory().get('/', HTTP_HOST='a.example')
        self.assertIsInstance(geocoding.get_geocoder(request), W30Geocoder)
        html = GeocodedAddressInput(point_field='location').render('address', '')
        self.assertIn('data-geocode-url', html)

    def test_a_callable_and_a_class(self):
        with override_settings(GT_GEOCODER=site_geocoder):
            self.assertEqual(self.search('a.example').status_code, 200)
        with override_settings(GT_GEOCODER=W30Geocoder,
                               GT_GEOCODER_OPTIONS={'prefix': 'Any'}):
            self.assertEqual(self.search('b.example').json()['results'][0]['label'],
                             'Any Centro')
            self.assertIsInstance(geocoding.get_geocoder(), W30Geocoder)
        with override_settings(GT_GEOCODER=42):
            with self.assertRaises(ImproperlyConfigured):
                geocoding.get_geocoder()
        with override_settings(GT_GEOCODER=None):
            self.assertFalse(geocoding.geocoder_configured())
            self.assertEqual(self.search('a.example').status_code, 404)


# -- metrics -----------------------------------------------------------------------

class W30MetricsTests(TTMBase):
    def setUp(self):
        super().setUp()
        self.requester = User.objects.create_user('req')
        start = timezone.localdate().replace(day=1)
        self.last_month = timezone.make_aware(
            timezone.datetime.combine(start - timedelta(days=5),
                                      timezone.datetime.min.time())) \
            + timedelta(hours=12)

    def purchase(self, amount, when=None):
        row = PurchaseRequest.objects.create(title='P', amount=Decimal(amount),
                                             requester=self.requester)
        if when is not None:
            PurchaseRequest.objects.filter(pk=row.pk).update(created_at=when)
        return row

    def test_a_card_without_a_period(self):
        self.purchase('30.00')
        self.purchase('20.00', self.last_month)
        page = self.publish(metrics(
            {'label': 'This month', 'fn': 'sum', 'column': 'amount'},
            {'label': 'Total', 'fn': 'sum', 'column': 'amount', 'period': 'all'},
            {'label': 'Year', 'fn': 'count', 'period': 'year', 'compare': False},
            date_field='created_at', period='month'), path='kpis')
        cards = {card['key']: card for card in self.json(page, 'kpis')['metrics']}
        self.assertEqual((cards['m0']['value'], cards['m0']['compare']), (30.0, True))
        self.assertEqual((cards['m1']['value'], cards['m1']['compare'],
                          cards['m1']['period_label']), (50.0, False, ''))
        self.assertEqual((cards['m2']['period'], cards['m2']['period_label']),
                         ('year', 'This year'))
        html = self.page_html('kpis')
        self.assertIn('This month &middot; This month', html)
        self.assertIn('Year &middot; This year', html)
        self.assertIn('>Total</div>', html)

    def test_what_resolve_checks(self):
        self.assertError(metrics({'label': 'n', 'fn': 'count', 'period': 'all'}),
                         'only when the node has a date_field')
        # "all" is the period of a card, not of the node.
        self.assertError(metrics(date_field='created_at', period='all'),
                         "'all' is not one of")

    def test_the_page_context_for_generated_code(self):
        self.purchase('30.00')
        resolved, errors = engine.resolve(design(metrics(
            {'label': 'Sum', 'fn': 'sum', 'column': 'amount'})))
        self.assertEqual(errors, [])
        build = resolved.nodes['kpis'].build
        request = RequestFactory().get('/', HTTP_HOST='a.example')
        request.user = self.user
        context = region_page_context(build, request, '/generated/kpis/')
        self.assertFalse(context['unavailable'])
        self.assertEqual(context['cards'][0]['value'], 30.0)
        self.assertIn('30.00', context['cards_html'])
        self.assertIn('/generated/kpis/', str(context['config']))
        request.user = User.objects.create_user('nobody')
        self.assertIsNone(region_page_context(build, request, '/generated/kpis/'))


# -- facets and charts without a published page ------------------------------------

@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS)
class W30FacetsTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        self.grant('demoapp.view_product', 'demoapp.view_productcategory')
        self.resolved, errors = engine.resolve(chart_page(chart(), table_props={
            'column_conditions': {'status': {'perm': 'demoapp.delete_product'}}}))
        self.assertEqual(errors, [])

    def request(self, **params):
        request = RequestFactory().get('/', params)
        request.user = self.user
        return request

    def test_chart_facet_filters_without_the_page(self):
        build = self.resolved.nodes['by_category'].build
        self.assertEqual(build.facet_conditions,
                         {'status': {'perm': 'demoapp.delete_product'}})
        request = self.request(gtfilters=json.dumps([STATUS_DRAFT]))
        self.assertFalse(hasattr(request, 'gtdesign_resolved'))
        with self.assertRaises(APIValidationError):
            factories.chart_facet_filters(build, request)
        self.grant('demoapp.delete_product')
        self.assertEqual(factories.chart_facet_filters(build, self.request(
            gtfilters=json.dumps([STATUS_DRAFT]))), [STATUS_DRAFT])

    def test_facets_viewset_for_without_the_page(self):
        panel = self.resolved.nodes['f'].build
        target = self.resolved.nodes['products'].build
        view = factories.facets_viewset_for(panel, target=target).as_view(
            {'get': 'facets'})
        response = view(self.request(params=json.dumps({}), columns='category'))
        self.assertEqual(response.status_code, 200)
        counts = {item['label']: item['count'] for item in response.data['category']}
        self.assertEqual(counts, {'Food': 2, 'Tools': 1})
        # Without a target nor a page: nothing to count.
        lost = factories.facets_viewset_for(panel).as_view({'get': 'facets'})
        self.assertEqual(lost(self.request(params='{}')).status_code, 404)
        context = facets_page_context(panel, self.request(), url='/gen/f/',
                                      target=target)
        self.assertEqual((context['url'], context['columns']), ('/gen/f/', 'category'))
        with self.assertRaises(ValueError):
            facets_page_context(panel, self.request())


# -- the small ones ----------------------------------------------------------------

@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS)
class W30SmallTests(DataDesignTestCase):
    def test_the_repr_of_a_source(self):
        source = ModelDataSource(Department, name='tests.w30.units')
        self.assertEqual(repr(source), '<ModelDataSource tests.w30.units>')

    def test_a_markdown_column(self):
        expose(SupportTicket)
        self.grant('demoapp.view_supportticket')
        SupportTicket.objects.create(subject='Printer',
                                     description='**Jammed** <script>x()</script>',
                                     reporter=self.user)
        page = self.publish(design(node('object_management', 'tickets', {
            'model': 'demoapp.SupportTicket', 'form': 'ticket',
            'list_fields': ['subject', 'description']}),
            forms={'ticket': {'model': 'demoapp.SupportTicket',
                              'fields': ['subject', 'description'],
                              'widgets': {'description': 'MarkdownInput'}}}),
            path='tickets')
        url = self.api(page, 'tickets')
        row = self.client.get(url).json()['data'][0]
        self.assertIn('<strong>Jammed</strong>', row['description_html'])
        self.assertNotIn('<script', row['description_html'])
        self.assertEqual(row['description'], '**Jammed** <script>x()</script>')
        template = self.client.get(url + 'detail_template/').json()['template']
        self.assertIn('<% it.description_html | safe %>', template)
        self.assertIn('<% it.subject %>', template)
        html = self.client.get(reverse('gt-design-page', args=['tickets'])
                               ).content.decode()
        self.assertIn('"markdown": true', html)
        self.assertEqual(GTMarkdownHTMLField().to_representation(''), '')

    def test_a_menu_link_to_a_design_page_with_a_slash(self):
        item = MenuItem(title='x', url_name='gt-design-page', is_reversed=True,
                        reversed_args='"sales/clients"')
        page_item = MenuItem(title='x', url_name='page:a/b')
        # Off by default: the links as they were.
        self.assertEqual(menu.item_url(item), '/designs/sales/clients')
        self.assertEqual(menu.item_url(page_item), '/designs/a/b')
        with override_settings(GT_MENU_DESIGN_PAGE_SLASH=True):
            self.assertEqual(menu.item_url(item), '/designs/sales/clients/')
            self.assertEqual(menu.item_url(page_item), '/designs/a/b/')
            other = MenuItem(title='x', url_name='flow_inbox', is_reversed=True,
                             reversed_args='"sales.order"')
            self.assertFalse(menu.item_url(other).endswith('/sales.order/'))
        # Both forms are the page.
        self.grant(*ALL_PRODUCT_PERMS)
        self.publish(design(node('html', 'hi', {'html': '<p>hi</p>'})), path='a/b')
        self.assertEqual(self.client.get('/designs/a/b/').status_code, 200)
        self.assertEqual(self.client.get('/designs/a/b').status_code, 200)

    def test_a_test_database_per_process(self):
        database = settings.DATABASES['default']
        if 'sqlite' not in database['ENGINE']:
            self.skipTest('the SQLite settings of the demo')
        # The pid of the process that loaded the settings (the parent of
        # the workers of --parallel, which clone it).
        self.assertRegex(str(database['TEST']['NAME']), r'test_db_\d+\.sqlite3$')


# -- the proposals of E12: hooks for the editor and mixins for generated code ------

class GeneratingContext(ResolveContext):
    """What the editor does: steps and pages it generates."""

    def pipeline_step(self, name, path=None, kind=None):
        if name.startswith('gen.'):
            return step_build(name, kind or 'validation', lambda ctx: None).process
        return super().pipeline_step(name, path)

    def branch_target(self, target, path=None, *, event=pipelines.ON_SUBMIT,
                      model=None):
        if target == 'page:generated':
            return BranchBuild(target, url='/generated/')
        return super().branch_target(target, path, event=event, model=model)


@override_settings(LANGUAGE_CODE='en')
class W30EditorHooksTests(TestCase):
    def resolve(self, stage, rctx=None):
        rctx = rctx or GeneratingContext({})
        found = pipelines.resolve_pipeline(
            rctx, {'pipeline': {'on_submit': stage}}, '$', event='on_submit',
            model=NewHire)
        return found, [str(error) for error in rctx.errors]

    def test_the_kind_in_the_document(self):
        found, errors = self.resolve({'steps': [
            {'name': 'gen.check', 'kind': 'validation'},
            {'name': 'gen.total', 'kind': 'computation'}]})
        self.assertEqual(errors, [])
        self.assertEqual([step.kind for step in found.steps],
                         ['validation', 'computation'])
        with self.assertRaisesMessage(ImproperlyConfigured, 'is a computation'):
            build_pipeline({'steps': [{'name': 'tests_w30.plate',
                                       'kind': 'process'}]}, model=NewHire)
        with self.assertRaises(ImproperlyConfigured):
            step_build('gen.x', 'magic', len)

    def test_a_branch_to_a_generated_page(self):
        found, errors = self.resolve({'branches': [{'to': 'page:generated'}]})
        self.assertEqual(errors, [])
        self.assertEqual(found.branches[0].url_for(), '/generated/')
        _found, errors = self.resolve({'branches': [{'to': 'page:generated'}]},
                                      ResolveContext({}))
        self.assertIn("no design page 'generated' is published", ' '.join(errors))
        self.assertTrue(any('.branches[0].to' in error for error in errors))

    def test_the_catalogue_says_the_app(self):
        entry = next(item for item in pipelines.catalogue()
                     if item['name'] == 'tests_w30.plate')
        self.assertEqual(entry['app'], 'djgentelella')


class UnitCreate(PipelineFormMixin, CreateView):
    model = Department
    fields = ['name', 'head']
    success_url = '/units/'
    pipeline = {'steps': [{'name': 'tests_w30.no_bob'}],
                'branches': [{'to': '/w30-done/',
                              'condition': {'perm': 'demoapp.delete_department'}}]}

    def form_invalid(self, form):
        return HttpResponse(str(form.errors), status=400)


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'head']


class UnitViewSet(PipelineViewSetMixin, viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = UnitSerializer
    model = Department
    pipeline = {'steps': [{'name': 'tests_w30.no_bob'}],
                'branches': [{'to': '/w30-done/'}]}


class PlainPage(View):
    def get(self, request):
        return JsonResponse(self.get_context_data())

    def get_context_data(self, **kwargs):
        return {}


class GreetingPage(PipelinePageMixin, PlainPage):
    pipeline = {'steps': [{'name': 'tests_w30.greet'}, {'name': 'tests_w30.deny'}]}


@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS)
class W30PipelineMixinsTests(TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('ana', password='pw')

    def test_a_form_view(self):
        def post(data):
            request = RequestFactory().post('/', data)
            request.user = self.user
            return UnitCreate.as_view()(request)

        response = post({'name': 'Bob', 'head': ''})
        self.assertEqual(response.status_code, 400)
        self.assertIn('No Bobs.', response.content.decode())
        self.assertFalse(Department.objects.exists())
        response = post({'name': 'Sales', 'head': ''})
        self.assertEqual(response['Location'], '/units/')
        self.user = grant(self.user, 'demoapp.delete_department')
        self.assertEqual(post({'name': 'Ops', 'head': ''})['Location'], '/w30-done/')
        self.assertEqual(Department.objects.count(), 2)

    def test_a_viewset(self):
        view = UnitViewSet.as_view({'post': 'create'})

        def post(data):
            request = APIRequestFactory().post('/', data, format='json')
            force_authenticate(request, self.user)
            return view(request)

        response = post({'name': 'Bob', 'head': ''})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['name'], ['No Bobs.'])
        response = post({'name': 'Sales', 'head': ''})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['gtdesign_redirect'], '/w30-done/')

    def test_a_page(self):
        request = RequestFactory().get('/')
        request.user = self.user
        response = GreetingPage.as_view()(request)
        self.assertEqual(json.loads(response.content),
                         {'pipeline': {'greeting': 'hello'}})
        request = RequestFactory().get('/', {'deny': '1'})
        request.user = self.user
        with self.assertRaises(PermissionDenied):
            GreetingPage.as_view()(request)
