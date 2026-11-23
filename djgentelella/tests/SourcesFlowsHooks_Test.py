"""The public hooks of datasources, flows and conditions.

``validate_params`` and the decimal checks of ``coerce_value``, the export
handler and the per-request exporter resolvers (datasources);
``human_task.form``, the registry API, the action policy and the tasks whose
object went away (flows); ``ConditionRequest`` as the way to evaluate on
behalf of a user (authorization conditions).
"""
import json
from decimal import Decimal
from unittest import mock

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import connection, models
from django.db.models.signals import post_delete
from django.http import HttpResponse
from django.template import Context, Template
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from demoapp.models import Country, ExpenseReport
from djgentelella.authorization import (
    ConditionRequest, authorization, check_authorization, evaluate_condition,
    set_flag,
)
from djgentelella.datasources import export as ds_export
from djgentelella.datasources import query
from djgentelella.datasources.base import (
    Column, ModelDataSource, register_datasource, unregister_datasource,
)
from djgentelella.designs.jsonschema import Error
from djgentelella.flows import (
    ARGUMENTS, COMMON, ActionNotAllowed, Flow, State, Transition,
    TransitionNotAllowed, action_blocked, build_flow, catalogue, get_flow,
    publish_definition, register_condition, register_flow, register_task_form,
    registered_actions, registered_conditions, registered_flows,
    registered_task_forms,
)
from djgentelella.flows import base as flows_base
from djgentelella.flows import definitions
from djgentelella.flows.exceptions import TaskNotAllowed
from djgentelella.flows.actions import (
    ActionContext, Notify, SetVariable, render, run_actions,
)
from djgentelella.flows.models import FlowInstance, Task, TaskHistory
from djgentelella.flows.taskforms import get_task_form, unregister_task_form
from djgentelella.flows.timers import process_due
from djgentelella.models import Notification

User = get_user_model()


def make_user(name, *codenames, groups=(), **extra):
    user = User.objects.create_user(name, password='x', **extra)
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
    for group in groups:
        user.groups.add(group)
    return user


# -- datasources -------------------------------------------------------------------
@override_settings(LANGUAGE_CODE='en')
class SourceCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = make_user('ana', 'view_expensereport')
        cls.expense = ExpenseReport.objects.create(
            title='Trip', amount=Decimal('120.50'), requester=cls.ana,
            manager=cls.ana)
        ExpenseReport.objects.create(title='Hotel', amount=Decimal('80'),
                                     requester=cls.ana, manager=cls.ana)

    def setUp(self):
        self.source = ModelDataSource(ExpenseReport, name='tests.sources.expenses',
                                      fields=['id', 'title', 'amount',
                                              'requester', 'paid'])
        register_datasource(self.source)
        self.addCleanup(unregister_datasource, 'tests.sources.expenses')
        self.request = RequestFactory().get('/')
        self.request.user = self.ana

    def url(self, endpoint=''):
        name = 'gtdatasource-' + endpoint if endpoint else 'gtdatasource'
        return reverse(name, args=['tests.sources.expenses'])


# English labels are asserted: the demo runs in Spanish once its .mo, which is
# not versioned, is compiled, and a local run would disagree with CI.
@override_settings(LANGUAGE_CODE='en')
class ValidateParamsTests(SourceCase):
    def test_a_valid_document_comes_back_normalized(self):
        clean, errors = query.validate_params(self.source, self.request, {
            'filters': [{'column': 'amount', 'op': 'gt', 'value': '100'}],
            'ordering': ['-amount'], 'columns': ['title', 'amount'],
            'group_by': ['requester'], 'aggregates': [{'column': 'amount',
                                                       'fn': 'sum'}],
            'pivot': {'rows': 'requester', 'columns': 'paid',
                      'value': {'fn': 'count'}},
            'highlights': [{'filter': {'column': 'paid', 'op': 'eq',
                                       'value': True}, 'css': 'table-danger'}]})
        self.assertEqual(errors, [])
        self.assertEqual(clean['search'], '')
        self.assertEqual(clean['columns'], ['title', 'amount'])

    def test_an_unknown_column_is_reported_with_its_path(self):
        clean, errors = query.validate_params(self.source, self.request, {
            'filters': [{'column': 'secret', 'op': 'eq', 'value': 1}],
            'columns': ['title', 'nope', 'title'], 'ordering': ['-ghost']})
        self.assertIsNone(clean)
        paths = [error.path for error in errors]
        self.assertEqual(paths, ['$.filters[0]', '$.ordering[0]', '$.columns[1]',
                                 '$.columns[2]'])
        self.assertIsInstance(errors[0], Error)
        self.assertIn('secret', errors[0].message)

    def test_invalid_aggregates_and_groups(self):
        _clean, errors = query.validate_params(self.source, self.request, {
            'aggregates': [{'column': 'title', 'fn': 'sum'},
                           {'column': 'amount', 'fn': 'median'},
                           {'column': 'amount', 'fn': ['sum']}, 'count'],
            'group_by': [{'column': 'title', 'period': 'month'},
                         {'column': 'amount', 'period': ['year']}],
            'pivot': {'rows': 'title'}})
        self.assertEqual([error.path for error in errors], [
            '$.group_by[0]', '$.group_by[1]', '$.aggregates[0]', '$.aggregates[1]',
            '$.aggregates[2]', '$.aggregates[3]', '$.pivot.columns'])

    def test_highlight_css_must_be_class_names(self):
        _clean, errors = query.validate_params(self.source, self.request, {
            'highlights': [{'filter': {'column': 'paid', 'op': 'eq', 'value': 1},
                            'css': '" onmouseover="alert(1)'}, {'css': 'x'}]})
        self.assertEqual([error.path for error in errors],
                         ['$.highlights[0].css', '$.highlights[1]'])

    def test_not_a_document(self):
        self.assertEqual(query.validate_params(self.source, self.request, '[1]'),
                         (None, [Error('$', 'The query parameters must be a JSON '
                                            'object.')]))

    def test_strict_refuses_unknown_keys(self):
        params = {'filters': [], 'mine': 1,
                  'aggregates': [{'column': 'amount', 'fn': 'sum', 'x': 1}]}
        self.assertEqual(query.validate_params(self.source, self.request,
                                               params)[1], [])
        _clean, errors = query.validate_params(self.source, self.request, params,
                                               strict=True)
        self.assertEqual([error.path for error in errors], ['$', '$.aggregates[0]'])

    def test_the_old_private_names_still_work(self):
        self.assertIs(query._group_expr, query.group_expr)
        self.assertIs(query._aggregate_expr, query.aggregate_expr)
        colmap = self.source.column_map(self.request)
        self.assertEqual(query.aggregate_expr(colmap, {'column': 'amount',
                                                       'fn': 'avg'})[0],
                         'amount__avg')
        with self.assertRaises(ValidationError):
            query.group_expr(colmap, {'column': 'title', 'period': 'week'})


class DecimalValueTests(SourceCase):
    def column(self, **kwargs):
        return Column('amount', 'Amount', 'decimal', **kwargs)

    def test_not_finite_is_a_validation_error(self):
        for value in ('NaN', 'nan', 'sNaN', 'Infinity', '-Infinity', 'inf',
                      float('nan'), float('inf')):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    query.coerce_value(self.column(), value)

    def test_out_of_the_range_of_the_field(self):
        column = self.source.column_map(self.request)['amount']
        self.assertEqual((column.max_digits, column.decimal_places), (12, 2))
        self.assertEqual(query.coerce_value(column, '9999999999.99'),
                         Decimal('9999999999.99'))
        self.assertEqual(query.coerce_value(column, '-0.001'), Decimal('-0.001'))
        for value in ('10000000000', '-1e10', '1e999999'):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    query.coerce_value(column, value)

    def test_without_a_size_only_the_generic_limits(self):
        self.assertEqual(query.coerce_value(self.column(), '1e300'), Decimal('1e300'))
        for value in ('1e1001', '1e-1001'):
            with self.assertRaises(ValidationError):
                query.coerce_value(self.column(), value)

    def test_the_api_answers_400_not_500(self):
        self.client.force_login(self.ana)
        for value in ('NaN', 'Infinity', '1e20', ['1', 'NaN']):
            op = 'between' if isinstance(value, list) else 'gt'
            params = json.dumps({'filters': [{'column': 'amount', 'op': op,
                                              'value': value}]})
            with self.subTest(value=value):
                response = self.client.get(self.url('rows'), {'params': params})
                self.assertEqual(response.status_code, 400)
        _clean, errors = query.validate_params(self.source, self.request, {
            'filters': [{'column': 'amount', 'op': 'in', 'value': ['1', 'NaN']}]})
        self.assertEqual([error.path for error in errors], ['$.filters[0]'])


def job_handler(request, source, params, fmt):
    if fmt == 'csv' and params['search'] == 'big':
        return HttpResponse('queued %s %s' % (source.name, fmt), status=202)
    return None


class ExportHandlerTests(SourceCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.ana)

    @override_settings(GT_DATASOURCE_EXPORT_HANDLER=job_handler)
    def test_the_handler_answers_or_lets_the_export_run(self):
        params = json.dumps({'search': 'big'})
        response = self.client.get(self.url('export'), {'fmt': 'csv',
                                                        'params': params})
        self.assertEqual((response.status_code, response.content),
                         (202, b'queued tests.sources.expenses csv'))
        response = self.client.get(self.url('export'), {'fmt': 'csv'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Trip', b''.join(response.streaming_content).decode())

    @override_settings(GT_DATASOURCE_EXPORT_HANDLER='djgentelella.tests.'
                       'SourcesFlowsHooks_Test.job_handler')
    def test_a_dotted_path_and_what_it_gets(self):
        seen = []

        def spy(request, source, params, fmt):
            seen.append((request.user, source.name, params['search'], fmt))
        with override_settings(GT_DATASOURCE_EXPORT_HANDLER=spy):
            self.client.get(self.url('export'), {'fmt': 'json', 'params':
                                                 json.dumps({'search': 'x'})})
        self.assertEqual(seen, [(self.ana, 'tests.sources.expenses', 'x', 'json')])
        response = self.client.post(self.url('export'), {'fmt': 'csv',
                                                         'search': 'big'},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 202)

    def test_an_unknown_format_is_refused_before_the_handler(self):
        handler = mock.Mock(return_value=HttpResponse('no'))
        with override_settings(GT_DATASOURCE_EXPORT_HANDLER=handler):
            response = self.client.get(self.url('export'), {'fmt': 'pdf:nope'})
        self.assertEqual(response.status_code, 400)
        handler.assert_not_called()

    def test_the_params_are_validated_before_the_handler(self):
        """A handler that queues a job would otherwise find a bad document
        only in the background: it is a 400 here, with every problem."""
        handler = mock.Mock(return_value=HttpResponse('queued', status=202))
        bad = json.dumps({'columns': ['title', 'nope'],
                          'aggregates': [{'column': 'title', 'function': 'sum'}]})
        with override_settings(GT_DATASOURCE_EXPORT_HANDLER=handler):
            response = self.client.get(self.url('export'), {'fmt': 'csv',
                                                            'params': bad})
            self.assertEqual(response.status_code, 400)
            detail = ' '.join(response.json()['detail'])
            self.assertIn('$.columns[1]', detail)
            self.assertIn('$.aggregates[0]', detail)
            handler.assert_not_called()
            with self.assertRaises(ValidationError):
                ds_export.handle_export(self.source, self.request,
                                        query.parse_params(bad), 'csv')
            handler.assert_not_called()
            good = json.dumps({'columns': ['title']})
            response = self.client.get(self.url('export'), {'fmt': 'csv',
                                                            'params': good})
        self.assertEqual(response.status_code, 202)
        handler.assert_called_once()

    def test_export_itself_never_calls_the_handler(self):
        handler = mock.Mock(return_value=HttpResponse('no'))
        with override_settings(GT_DATASOURCE_EXPORT_HANDLER=handler):
            response = ds_export.export(self.source, self.request, {}, 'json')
        self.assertEqual(json.loads(response.content)['source'],
                         'tests.sources.expenses')
        handler.assert_not_called()


def layout_exporter(source, request, params):
    return HttpResponse('layout of %s' % source.name, content_type='text/plain')


def app_layouts(request):
    """The 'pdf:invoice' layout belongs to the requests of one application."""
    if getattr(request, 'META', {}).get('HTTP_X_APP') == 'sales':
        return {'pdf:invoice': layout_exporter}
    return {}


class ExporterResolverTests(SourceCase):
    def setUp(self):
        super().setUp()
        ds_export.register_exporter_resolver(app_layouts)
        self.addCleanup(ds_export.unregister_exporter_resolver, app_layouts)
        self.client.force_login(self.ana)

    def test_the_format_only_exists_for_its_request(self):
        info = self.client.get(self.url()).json()
        self.assertNotIn('pdf:invoice', info['formats'])
        self.assertIn('csv', info['formats'])
        info = self.client.get(self.url(), HTTP_X_APP='sales').json()
        self.assertIn('pdf:invoice', info['formats'])
        self.assertEqual(info['formats'], sorted(info['formats']))
        self.assertEqual(ds_export.available_formats(
            RequestFactory().get('/', HTTP_X_APP='sales')),
            ['csv', 'xlsx', 'json', 'pdf', 'pdf:invoice'])
        response = self.client.get(self.url('export'), {'fmt': 'pdf:invoice'},
                                   HTTP_X_APP='sales')
        self.assertEqual(response.content, b'layout of tests.sources.expenses')
        response = self.client.get(self.url('export'), {'fmt': 'pdf:invoice'})
        self.assertEqual(response.status_code, 400)
        with self.assertRaises(ValidationError):
            ds_export.export(self.source, self.request, {}, 'pdf:invoice')

    def test_the_export_menu_lists_the_request_formats(self):
        template = Template("{% load gtdatasources %}"
                            "{% gt_datasource_export 'tests.sources.expenses' %}")
        sales = RequestFactory().get('/', HTTP_X_APP='sales')
        html = template.render(Context({'request': sales}))
        self.assertIn('pdf:invoice', html)
        html = template.render(Context({'request': RequestFactory().get('/')}))
        self.assertNotIn('pdf:invoice', html)
        self.assertIn('csv', html)
        html = Template("{% load gtdatasources %}{% gt_datasource_export "
                        "'tests.sources.expenses' 'csv' %}").render(
            Context({'request': sales}))
        self.assertIn('data-formats="csv"', html)

    def test_a_resolver_that_fails_takes_nothing_down(self):
        def broken(request):
            raise RuntimeError('boom')
        ds_export.register_exporter_resolver(broken)
        self.addCleanup(ds_export.unregister_exporter_resolver, broken)
        with self.assertLogs('djgentelella.datasources.export', 'ERROR'):
            formats = ds_export.available_formats(self.request)
        self.assertIn('csv', formats)


# -- flows: human_task.form ------------------------------------------------------
@register_task_form('tests.sources.review')
class ReviewForm(forms.Form):
    amount = forms.DecimalField(max_digits=8, decimal_places=2)
    note = forms.CharField(required=False)


REVIEW_FLOW = {
    'schema_version': 2, 'name': 'tests.sources.review', 'model': 'demoapp.Country',
    'title': 'Review', 'initial': 'draft',
    'states': [
        {'id': 'draft', 'type': 'state'},
        {'id': 'review', 'type': 'human_task', 'title': 'Review {{ object }}',
         'groups': ['Reviewers'], 'form': 'tests.sources.review',
         'outcomes': {'approve': 'done', 'reject': 'draft'}},
        {'id': 'done', 'type': 'state'},
    ],
    'transitions': [{'name': 'submit', 'source': 'draft', 'target': 'review'}],
    'variables': {'note': 'from the variables'},
}


@override_settings(LANGUAGE_CODE='en')
class FlowCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reviewers = Group.objects.create(name='Reviewers')
        cls.ben = make_user('ben', 'view_country', groups=[cls.reviewers])
        cls.root = User.objects.create_superuser('sourcesroot', password='x')
        cls.definition = publish_definition(REVIEW_FLOW)

    def start(self, name='Peru'):
        country = Country.objects.create(name=name)
        flow = get_flow('tests.sources.review')
        flow.run(country, 'submit', self.root)
        return country, Task.objects.get(object_id=str(country.pk), state__in=Task.OPEN)


class TaskFormTests(FlowCase):
    def setUp(self):
        self.client.force_login(self.ben)

    def test_the_activity_resolves_the_registered_form(self):
        flow = get_flow('tests.sources.review')
        self.assertIs(flow.activities['review'].form, ReviewForm)
        self.assertIn('form', ARGUMENTS['human_task'])
        self.assertIs(get_task_form(ReviewForm), ReviewForm)

    def test_an_unknown_form_does_not_publish(self):
        document = json.loads(json.dumps(REVIEW_FLOW))
        document['states'][1]['form'] = 'os.system'
        # A stored document still loads: the activity refuses when the flow
        # reaches it (IntegrationTaskFormAllowlist_Test).
        self.assertIsNone(build_flow(document).activities['review'].form)
        with self.assertRaisesMessage(ImproperlyConfigured, '$.states[1].form'):
            publish_definition(document)
        document['states'][0]['form'] = 'tests.sources.review'  # not a human task
        with self.assertRaises(ImproperlyConfigured):
            build_flow(document)

    def test_the_page_shows_it_with_the_variables_as_initial(self):
        _country, task = self.start()
        page = self.client.get(reverse('task_detail', args=[task.pk]))
        self.assertContains(page, 'name="task-amount"')
        self.assertContains(page, 'value="from the variables"')

    def test_an_invalid_form_keeps_the_task_open(self):
        country, task = self.start()
        response = self.client.post(reverse('task_action', args=[task.pk, 'complete']),
                                    {'outcome': 'approve', 'task-amount': 'lots',
                                     'complete-comment': ''})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'name="task-amount"', status_code=400)
        task.refresh_from_db()
        self.assertEqual(task.state, Task.UNASSIGNED)
        self.assertEqual(get_flow('tests.sources.review').state(country), 'review')

    def test_a_valid_form_writes_the_variables(self):
        country, task = self.start()
        response = self.client.post(reverse('task_action', args=[task.pk, 'complete']),
                                    {'outcome': 'approve', 'task-amount': '12.5',
                                     'task-note': 'fine'})
        self.assertEqual(response.status_code, 302)
        instance = get_flow('tests.sources.review').get_instance(country, create=False)
        self.assertEqual(instance.state, 'done')
        self.assertEqual(instance.variables['amount'], '12.5')
        self.assertEqual(instance.variables['note'], 'fine')
        self.assertEqual(instance.variables['review_outcome'], 'approve')

    def test_a_task_without_a_form_is_unchanged(self):
        _country, task = self.start()
        loose = Task.objects.create(title='Loose', object_id='')
        loose.groups.add(self.reviewers)
        page = self.client.get(reverse('task_detail', args=[loose.pk]))
        self.assertNotContains(page, 'name="task-amount"')
        response = self.client.post(reverse('task_action', args=[loose.pk,
                                                                 'complete']),
                                    {'outcome': 'approve'})
        self.assertEqual(response.status_code, 302)
        loose.refresh_from_db()
        self.assertEqual(loose.state, Task.COMPLETED)

    def test_the_decorator_forms(self):
        @register_task_form
        class Bare(forms.Form):
            ok = forms.BooleanField()
        name = '%s.%s' % (Bare.__module__, Bare.__qualname__)
        self.addCleanup(unregister_task_form, name)
        self.assertIs(get_task_form(name), Bare)
        with self.assertRaises(ImproperlyConfigured):
            register_task_form('x')(object)


# -- flows: the registry -----------------------------------------------------------
@register_condition('tests.sources.always')
def always(context):
    """Always true, for the catalogue."""
    return True


class SourcesPythonFlow(Flow):
    name = 'tests.sources.python'
    title = 'Declared in Python'
    model = Country
    states = [('a', 'A'), ('b', 'B')]
    initial = 'a'
    transitions = [Transition('go', 'a', 'b')]


register_flow(SourcesPythonFlow)


class RegistryTests(FlowCase):
    def test_everything_is_json(self):
        document = catalogue(published=True)
        self.assertEqual(json.loads(json.dumps(document)), document)
        self.assertEqual(set(document), {'schema_version', 'activities', 'actions',
                                         'conditions', 'task_forms', 'flows'})

    def test_actions_with_their_props_schema(self):
        actions = {item['name']: item for item in registered_actions()}
        self.assertEqual(actions['set_field']['props_schema']['required'], ['field'])
        self.assertTrue(actions['set_field']['help'])
        self.assertEqual([item['name'] for item in registered_actions()],
                         sorted(actions))

    def test_conditions_and_task_forms(self):
        conditions = {item['name']: item for item in registered_conditions()}
        self.assertEqual(conditions['tests.sources.always']['help'],
                         'Always true, for the catalogue.')
        forms_ = {item['name']: item for item in registered_task_forms()}
        self.assertEqual([field['name'] for field in
                          forms_['tests.sources.review']['fields']], ['amount', 'note'])
        self.assertEqual(forms_['tests.sources.review']['fields'][0]['type'],
                         'DecimalField')

    def test_python_flows_without_the_database(self):
        with self.assertNumQueries(0):
            flows = {item['name']: item for item in registered_flows()}
        self.assertEqual(flows['tests.sources.python']['source'], 'python')
        self.assertEqual(flows['tests.sources.python']['model'], 'demoapp.Country')
        self.assertEqual(flows['tests.sources.python']['transitions'], ['go'])
        self.assertNotIn('tests.sources.review', flows)
        published = {item['name']: item for item in registered_flows(published=True)}
        self.assertEqual(published['tests.sources.review']['source'], 'definition')
        self.assertEqual(published['tests.sources.review']['versions'], [1])

    def test_common_and_arguments_are_the_engine_s(self):
        self.assertIs(COMMON, definitions.COMMON)
        self.assertIs(ARGUMENTS, definitions.ARGUMENTS)
        activities = catalogue()['activities']
        self.assertEqual(activities['common'], list(COMMON))
        self.assertEqual(activities['types']['human_task'],
                         list(ARGUMENTS['human_task']))


# -- flows: the action policy ------------------------------------------------------
def no_notifications(action, context):
    return action.name != 'notify'


class OnlyVariables:
    def allowed(self, action, context):
        return action.name == 'set_variable'


class PolicyFlow(Flow):
    name = 'tests.sources.policy'
    model = Country
    states = [('a', 'A'), ('b', 'B')]
    initial = 'a'
    transitions = [Transition('go', 'a', 'b', actions=[
        SetVariable('seen', True), Notify('{{ object }} moved', to='actor')])]


register_flow(PolicyFlow)


# English labels are asserted: the demo runs in Spanish once its .mo, which is
# not versioned, is compiled, and a local run would disagree with CI.
@override_settings(LANGUAGE_CODE='en')
class ActionPolicyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = make_user('ana_policy', 'view_country')
        cls.country = Country.objects.create(name='Chile')

    def context(self, **kwargs):
        return ActionContext(obj=self.country, user=self.ana, **kwargs)

    @override_settings(GT_FLOWS_ACTION_POLICY=no_notifications)
    def test_the_setting_blocks_and_audits(self):
        blocked = []

        def receiver(sender, action, context, reason, **kwargs):
            blocked.append((sender, action.name, context.obj, reason))
        action_blocked.connect(receiver)
        self.addCleanup(action_blocked.disconnect, receiver)
        context = self.context()
        with self.assertLogs('djgentelella.flows.actions', 'WARNING') as logs:
            with self.assertRaises(ActionNotAllowed):
                run_actions([SetVariable('a', 1), Notify('hi')], context)
        self.assertIn('notify', logs.output[0])
        self.assertEqual(context.variables, {'a': 1})
        self.assertEqual(blocked[0][:3], (Notify, 'notify', self.country))
        self.assertFalse(Notification.objects.exists())

    @override_settings(GT_FLOWS_ACTION_POLICY='djgentelella.tests.'
                       'SourcesFlowsHooks_Test.no_notifications')
    def test_a_refused_action_refuses_the_transition(self):
        flow = get_flow('tests.sources.policy')
        with self.assertLogs('djgentelella.flows.actions', 'WARNING'):
            with self.assertRaises(TransitionNotAllowed):
                flow.run(self.country, 'go', self.ana)
        self.assertEqual(flow.state(self.country), 'a')

    def test_the_context_policy_and_the_setting_both_apply(self):
        context = self.context(policy=OnlyVariables())
        run_actions([SetVariable('a', 1)], context)
        with self.assertLogs('djgentelella.flows.actions', 'WARNING'):
            with self.assertRaises(ActionNotAllowed):
                run_actions([Notify('hi')], context)
        with override_settings(GT_FLOWS_ACTION_POLICY=lambda a, c: False):
            with self.assertLogs('djgentelella.flows.actions', 'WARNING'):
                with self.assertRaises(ActionNotAllowed):
                    run_actions([SetVariable('a', 2)], context)
        self.assertEqual(context.variables, {'a': 1})

    def test_a_policy_that_raises_refuses(self):
        def broken(action, context):
            raise RuntimeError('broken policy')
        with self.assertLogs('djgentelella.flows.actions', 'WARNING') as logs:
            with self.assertRaises(ActionNotAllowed) as raised:
                run_actions([SetVariable('a', 1)], self.context(policy=broken))
        # The detail stays in the log; the reason the user may see is generic.
        self.assertNotIn('broken policy', str(raised.exception))
        self.assertIn('is not allowed here', str(raised.exception))
        self.assertIn('broken policy', '\n'.join(logs.output))

    def test_a_policy_may_refuse_with_its_own_reason(self):
        def explains(action, context):
            raise ActionNotAllowed('Variables are read only here.')
        with self.assertLogs('djgentelella.flows.actions', 'WARNING'):
            with self.assertRaises(ActionNotAllowed) as raised:
                run_actions([SetVariable('a', 1)], self.context(policy=explains))
        self.assertEqual(str(raised.exception), 'Variables are read only here.')

    def test_without_policy_everything_runs(self):
        context = self.context()
        run_actions([SetVariable('a', 1), Notify('hi')], context)
        self.assertTrue(Notification.objects.filter(user=self.ana).exists())

    def test_the_render_context_hook(self):
        def reduced(context):
            return {'object': str(context.obj)}
        context = self.context(render_context=reduced,
                               variables={'secret': 's3cr3t'})
        self.assertEqual(render('{{ object }}:{{ variables.secret }}:{{ user }}',
                                context), 'Chile::')
        Notify('{{ object }} {{ user.username }}').run(context)
        self.assertEqual(Notification.objects.get(user=self.ana).description,
                         'Chile ')
        full = self.context(variables={'secret': 's3cr3t'})
        self.assertEqual(render('{{ variables.secret }}', full), 's3cr3t')


# -- flows: tasks whose object went away -------------------------------------------
# English labels are asserted: the demo runs in Spanish once its .mo, which is
# not versioned, is compiled, and a local run would disagree with CI.
@override_settings(LANGUAGE_CODE='en')
class OrphanTaskTests(FlowCase):
    def forget_the_flow(self):
        """What a fresh process knows: no JSON flow built, no receiver."""
        flows_base._built.clear()
        post_delete.disconnect(sender=Country,
                               dispatch_uid='gtflows-delete-demoapp.country')
        self.addCleanup(flows_base.watch_deletes, Country)

    def test_deleting_the_object_cancels_its_tasks_in_a_fresh_process(self):
        country, task = self.start()
        self.forget_the_flow()
        # What a process does when it opens its first database connection.
        flows_base.watch_definition_models(force=True)
        country.delete()
        task.refresh_from_db()
        self.assertEqual(task.state, Task.CANCELLED)
        self.assertIsNone(task.instance)
        self.assertEqual(TaskHistory.objects.filter(task=task).last().action,
                         'cancel')
        self.assertFalse(FlowInstance.objects.filter(flow='tests.sources.review')
                         .exists())
        self.assertFalse(Task.objects.inbox(self.ben).exists())

    def test_the_connection_hook_watches_the_published_models(self):
        self.forget_the_flow()
        self.assertFalse(post_delete.has_listeners(Country))
        fake = mock.Mock(alias=connection.alias, in_atomic_block=False)
        with mock.patch.dict(flows_base._watch, {'checked_at': None}):
            flows_base._on_connection(sender=None, connection=fake)
        self.assertTrue(post_delete.has_listeners(Country))

    def test_completing_an_orphan_task_is_refused_not_a_500(self):
        country, task = self.start()
        self.forget_the_flow()
        country.delete()  # nobody listening: the task stays open
        task.refresh_from_db()
        self.assertTrue(task.is_open)
        self.client.force_login(self.ben)
        response = self.client.post(reverse('task_action', args=[task.pk, 'complete']),
                                    {'outcome': 'approve', 'task-amount': '1'},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no longer exists')
        task.refresh_from_db()
        self.assertEqual(task.state, Task.CANCELLED)
        page = self.client.get(reverse('task_detail', args=[task.pk]))
        self.assertEqual(page.status_code, 200)

    def test_an_orphan_task_past_due_is_cancelled(self):
        country, task = self.start()
        Task.objects.filter(pk=task.pk).update(
            due=task.created_at, on_expire={'outcome': 'reject'})
        self.forget_the_flow()
        country.delete()
        self.assertEqual(process_due(), {'task_cancelled': 1})
        task.refresh_from_db()
        self.assertEqual(task.state, Task.CANCELLED)

    def test_a_default_manager_that_hides_the_object_forgets_nothing(self):
        """A soft-delete (or archived, or by Site) default manager hides the
        object: it still exists, so its instance and log are kept."""
        country, task = self.start(name='Hidden Peru')

        class Hiding(models.Manager):
            def get_queryset(self):
                return super().get_queryset().exclude(name__startswith='Hidden')
        hiding = Hiding()
        hiding.model = Country
        Task.objects.filter(pk=task.pk).update(
            due=task.created_at, on_expire={'outcome': 'reject'})
        task.refresh_from_db()
        instance = task.instance
        logged = instance.log.count()
        self.assertTrue(logged)
        with mock.patch.object(Country._meta, 'default_manager', hiding):
            self.assertFalse(Country._default_manager.filter(pk=country.pk)
                             .exists())
            self.assertTrue(instance.object_exists())
            # The engine does not run on a hidden object, but neither
            # completing the task nor its timer forgets anything.
            with self.assertRaises(TaskNotAllowed):
                task.complete(self.root, 'approve', check=False)
            with self.assertRaises(TaskNotAllowed):
                Task.objects.get(pk=task.pk).expire()
        task.refresh_from_db()
        self.assertTrue(task.is_open)
        self.assertEqual(task.instance_id, instance.pk)
        self.assertEqual(FlowInstance.objects.get(pk=instance.pk).log.count(),
                         logged)
        # Visible again, the flow goes on.
        task.complete(self.root, 'approve', check=False)
        self.assertEqual(task.state, Task.COMPLETED)
        Country.objects.filter(pk=country.pk).delete()
        self.assertFalse(instance.object_exists())

    def test_python_flows_keep_working(self):
        country = Country.objects.create(name='Bolivia')
        flow = get_flow('tests.sources.python')
        flow.run(country, 'go', self.root)
        country.delete()
        self.assertFalse(FlowInstance.objects.filter(flow='tests.sources.python')
                         .exists())


# -- authorization conditions: ConditionRequest ---------------------------------------
@authorization('tests.sources.from_query', cache=False)
def from_query(request, obj=None):
    """Reads what a real request has: it must not break outside one."""
    return request.GET.get('ok') == '1' or request.user.is_staff


class ConditionRequestTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site = Site.objects.create(domain='sources.example', name='Sources')
        cls.viewer = make_user('viewer_sources', 'view_country')
        cls.staff = make_user('staff_sources', is_staff=True)

    def test_on_behalf_of_a_user_and_a_site(self):
        set_flag('sources_beta', True, site=self.site)
        request = ConditionRequest(user=self.viewer, site=self.site)
        self.assertTrue(evaluate_condition({'all': [
            {'perm': 'demoapp.view_country'}, {'flag': 'sources_beta'}]}, request))
        self.assertFalse(evaluate_condition({'flag': 'sources_beta'},
                                            ConditionRequest(user=self.viewer)))

    def test_a_site_id_is_the_site(self):
        self.assertEqual(ConditionRequest(site=self.site.pk).site, self.site)
        self.assertEqual(ConditionRequest(site=str(self.site.pk)).site, self.site)
        self.assertIsNone(ConditionRequest(site=None).site)
        # An id of no Site fails: it is never the global scope.
        with self.assertRaisesMessage(ValueError, 'There is no Site with id 999999'):
            ConditionRequest(site=999999)
        with self.assertRaises(ValueError):
            ConditionRequest(site='999999')
        with self.assertRaises(ValueError):
            ConditionRequest(site='not a site')

    def test_the_system_is_anonymous(self):
        system = ConditionRequest()
        self.assertIsInstance(system.user, AnonymousUser)
        self.assertFalse(evaluate_condition({'perm': 'demoapp.view_country'},
                                            system))
        self.assertTrue(system.is_condition_request)

    def test_authorizations_that_read_the_request(self):
        self.assertFalse(check_authorization('tests.sources.from_query',
                                             ConditionRequest(self.viewer)))
        self.assertTrue(check_authorization('tests.sources.from_query',
                                            ConditionRequest(self.staff)))
        self.assertEqual(ConditionRequest().META, {})
        self.assertIsNone(ConditionRequest().method)

    def test_flow_conditions_use_it_outside_a_request(self):
        flow = Flow(name='tests.sources.conditions', model=Country,
                    states=[State('a'), State('b')],
                    initial='a', transitions=[Transition(
                        'go', 'a', 'b', condition={'perm': 'demoapp.view_country'})])
        country = Country.objects.create(name='Ecuador')
        self.assertTrue(flow.check(flow.get_transition('go'), country,
                                   self.viewer)[0])
        self.assertFalse(flow.check(flow.get_transition('go'), country,
                                    self.staff)[0])
