"""The pipeline of a design page (W27, C18): steps registered by name
(validations, computations, processes), ``props.pipeline.on_submit`` of the
components with a form and ``before_render`` of the page, the transaction,
the branches and what publishing refuses."""

import copy
import logging
from decimal import Decimal
from unittest import mock

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.contrib.sites.models import Site
from django.test import RequestFactory, override_settings
from django.urls import reverse

from demoapp.models import ShopItem, ShopOrder
from djgentelella.authorization import authorization
from djgentelella.designs import engine, factories, pipeline, publishing
from djgentelella.designs.pipeline import (
    PipelineContext, PipelineError, process, register_process, run_pipeline,
    unregister_process,
)
from djgentelella.tests.Designs_Test import design, node
from djgentelella.tests.DesignsData_Test import DataDesignTestCase, load
from djgentelella.tests.Locking_Test import lock_meta

ORDER_PERMS = ['demoapp.%s_shoporder' % action
               for action in ('view', 'add', 'change', 'delete')]
#: Something only the form carries: it must never reach the log.
SECRET_QUANTITY = 4321

#: The steps the tests call, in the order they ran.
calls = []


@authorization('tests.pp.big_order')
def big_order(request, obj=None):
    return obj is not None and obj.quantity >= 10


@authorization('tests.pp.never')
def never(request, obj=None):
    return False


@process('tests_pp.check_stock', kind='validation')
def check_stock(ctx):
    calls.append('check_stock')
    item, quantity = ctx.data.get('item'), ctx.data.get('quantity')
    if item is not None and quantity is not None and quantity > item.stock:
        ctx.add_error('quantity', 'Only %d in stock' % item.stock)


@process('tests_pp.positive', kind='validation')
def positive(ctx):
    calls.append('positive')
    if not ctx.data.get('quantity'):
        raise ValidationError('An order of nothing')


@process('tests_pp.total', kind='computation')
def total(ctx):
    calls.append('total')
    return {'total': ctx.data['item'].price * ctx.data['quantity']}


@process('tests_pp.take_stock', kind='process')
def take_stock(ctx, extra=0):
    calls.append('take_stock')
    order = ctx.instance
    ShopItem.objects.filter(pk=order.item_id).update(
        stock=order.item.stock - order.quantity - extra)


@process('tests_pp.explode', kind='process')
def explode(ctx):
    calls.append('explode')
    raise RuntimeError('quantity was %s' % ctx.data.get('quantity'))


@process('tests_pp.refuse', kind='process')
def refuse(ctx):
    calls.append('refuse')
    raise ValidationError('The warehouse said no', code='warehouse')


@register_process('tests_pp.greet', kind='computation',
                  schema={'type': 'object', 'required': ['word'],
                          'additionalProperties': False,
                          'properties': {'word': {'type': 'string'}}})
def greet(ctx, word):
    calls.append('greet')
    ctx.add_context(greeting=word)


@process('tests_pp.to_login', kind='process')
def to_login(ctx):
    calls.append('to_login')
    ctx.redirect('/accounts/login/')


@process('tests_pp.touch_version', kind='computation')
def touch_version(ctx):
    calls.append('touch_version')
    ctx.set_value('quantity', 1)


@process('tests_pp.touch_outside', kind='computation')
def touch_outside(ctx):
    ctx.set_value('total', 1)


def order_form():
    return {'order': {'model': 'demoapp.ShopOrder', 'fields': ['item', 'quantity']}}


def stage(*steps, branches=None):
    value = {'steps': [step if isinstance(step, dict) else {'name': step}
                       for step in steps]}
    if branches is not None:
        value['branches'] = branches
    return value


def crud(on_submit=None, **props):
    if on_submit is not None:
        props['pipeline'] = {'on_submit': on_submit}
    return design(node('crud_classic', 'orders', {
        'model': 'demoapp.ShopOrder', 'form': 'order',
        'views': ['list', 'create', 'update', 'detail'], **props}),
        forms=order_form())


def table(on_submit=None, **props):
    if on_submit is not None:
        props['pipeline'] = {'on_submit': on_submit}
    return design(node('object_management', 'orders', {
        'model': 'demoapp.ShopOrder', 'form': 'order', **props}),
        forms=order_form())


def with_page_pipeline(document, before_render):
    document = copy.deepcopy(document)
    document['root']['props'] = {'pipeline': {'before_render': before_render}}
    return document


def plain_page(url, **meta):
    return design(node('html', 'hello', {'html': '<p>hello</p>'}),
                  url=url, url_name=url.strip('/').replace('/', '_'), **meta)


#: Listed out of order on purpose: they run validation, computation, process.
ORDER_STEPS = stage('tests_pp.take_stock',
                    {'name': 'tests_pp.total', 'writes': ['total']},
                    'tests_pp.check_stock')


@override_settings(LANGUAGE_CODE='en')
class PPTestCase(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        calls.clear()
        self.grant(*ORDER_PERMS)
        self.notebook = ShopItem.objects.create(name='Notebook', price=Decimal('3.50'),
                                                stock=5)

    def crud_page(self, on_submit=None, path='orders', **props):
        page = self.publish(crud(on_submit, **props), path=path)
        return self.api(page, 'orders')

    def table_page(self, on_submit=None, path='orders-table', **props):
        page = self.publish(table(on_submit, **props), path=path)
        return self.api(page, 'orders')

    def stock(self):
        return ShopItem.objects.get(pk=self.notebook.pk).stock

    def order(self, quantity):
        return {'item': self.notebook.pk, 'quantity': quantity}


class PPRegistryTests(PPTestCase):
    def test_a_step_is_registered_by_name_and_kind(self):
        found = pipeline.get_process('tests_pp.check_stock')
        self.assertEqual((found.name, found.kind), ('tests_pp.check_stock',
                                                    'validation'))
        self.assertIs(found.function, check_stock)
        self.assertIn('tests_pp.greet',
                      pipeline.registered_processes('computation'))
        self.assertNotIn('tests_pp.greet',
                         pipeline.registered_processes('process'))
        entry = [item for item in pipeline.catalogue()
                 if item['name'] == 'tests_pp.greet'][0]
        self.assertEqual(entry['schema']['required'], ['word'])

    def test_names_and_kinds_are_checked(self):
        for name in ('nodot', 'app.', '.name', 'app.na-me', 'app.na me', 3):
            with self.assertRaises(ImproperlyConfigured, msg=name):
                register_process(name, check_stock, kind='validation')
        with self.assertRaises(ImproperlyConfigured):
            register_process('tests_pp.bad', check_stock, kind='magic')
        with self.assertRaises(ImproperlyConfigured):
            register_process('tests_pp.bad', 'not callable', kind='process')

    def test_registering_again_replaces_and_changes_the_generation(self):
        before = pipeline.generation()
        register_process('tests_pp.tmp', check_stock, kind='validation')
        register_process('tests_pp.tmp', explode, kind='process')
        self.assertEqual(pipeline.get_process('tests_pp.tmp').kind, 'process')
        unregister_process('tests_pp.tmp')
        self.assertIsNone(pipeline.get_process('tests_pp.tmp'))
        self.assertEqual(pipeline.generation(), before + 3)


class PPValidationTests(PPTestCase):
    """What publishing refuses: errors of the document, never of a request."""

    def test_the_demo_pages_publish(self):
        self.publish(load('shop_order_done'))
        self.publish(load('shop_orders'))

    def test_an_unregistered_step_is_refused_when_publishing(self):
        page, errors = publishing.publish(crud(stage('tests_pp.nope')), path='x')
        self.assertIsNone(page)
        self.assertEqual([error.path for error in errors],
                         ['$.root.children[0].children[0].children[0].props'
                          '.pipeline.on_submit.steps[0].name'])
        self.assertIn('tests_pp.nope', errors[0].message)

    def test_a_name_that_could_be_imported_is_not_imported(self):
        errors = self.errors(crud(stage('os.system')))
        self.assertEqual(len(errors), 1)
        self.assertIn("no pipeline step 'os.system'", errors[0])

    def test_params_are_checked_against_the_schema_of_the_step(self):
        self.assertEqual(self.errors(crud(stage(
            {'name': 'tests_pp.greet', 'params': {'word': 'hi'}}))), [])
        for params in ({}, {'word': 3}, {'word': 'hi', 'other': 1}):
            errors = self.errors(crud(stage(
                {'name': 'tests_pp.greet', 'params': params})))
            self.assertEqual(len(errors), 1, params)
            self.assertIn('.steps[0].params', errors[0])
        errors = self.errors(crud(stage(
            {'name': 'tests_pp.check_stock', 'params': {'any': 1}})))
        self.assertIn('unexpected property', errors[0])

    def test_writes_only_names_fields_a_computation_may_set(self):
        self.assertEqual(self.errors(crud(ORDER_STEPS)), [])
        for writes, text in ((['nope'], 'no field'), (['id'], 'not a field'),
                             (['created'], 'not a field'),
                             (['total', 'total'], 'twice')):
            errors = self.errors(crud(stage(
                {'name': 'tests_pp.total', 'writes': writes})))
            self.assertTrue(errors, writes)
            self.assertIn(text, ' '.join(errors))
        errors = self.errors(crud(stage(
            {'name': 'tests_pp.check_stock', 'writes': ['total']})))
        self.assertIn('only a computation sets fields', errors[0])

    def test_a_computation_cannot_declare_the_version_of_the_lock(self):
        with mock.patch.object(ShopOrder, 'GTLockMeta', lock_meta('total'),
                               create=True):
            errors = self.errors(crud(stage(
                {'name': 'tests_pp.total', 'writes': ['total']})))
        self.assertEqual(len(errors), 1)
        self.assertIn('version of optimistic locking', errors[0])

    def test_conditions_of_steps_and_branches_are_checked(self):
        errors = self.errors(crud(stage(
            {'name': 'tests_pp.total', 'condition': {'magic': 1}},
            branches=[{'to': '/x/', 'condition': {'perm': 3}}])))
        self.assertEqual(len(errors), 2)

    def test_the_default_branch_goes_last(self):
        errors = self.errors(crud(stage(branches=[{'to': '/a/'}, {'to': '/b/'}])))
        self.assertEqual(len(errors), 1)
        self.assertIn('branches[0]', errors[0])
        self.assertIn('only the last branch', errors[0])

    def test_branch_targets_must_exist(self):
        self.publish(plain_page('done/'), path='done')
        self.assertEqual(self.errors(crud(stage(branches=[
            {'to': 'page:done', 'condition': {'auth': 'tests.pp.big_order'}},
            {'to': '/elsewhere/'}]))), [])
        for to in ('page:missing', 'no_such_url_name', '//evil.example.com/x',
                   'https://evil.example.com/', 'flow:nope'):
            errors = self.errors(crud(stage(branches=[{'to': to}])))
            self.assertEqual(len(errors), 1, to)
            self.assertIn('.branches[0].to', errors[0])

    def test_a_branch_to_a_page_about_another_model_is_refused(self):
        self.publish(plain_page('product/', parent={'model': 'demoapp.Product'}),
                     path='product')
        errors = self.errors(crud(stage(branches=[{'to': 'page:product'}])))
        self.assertIn('is about one demoapp.Product', errors[0])

    def test_before_render_cannot_loop_back_to_its_page(self):
        own = with_page_pipeline(plain_page('loop/'),
                                 stage(branches=[{'to': 'page:loop'}]))
        errors = self.errors(own)
        self.assertEqual(len(errors), 1)
        self.assertIn('redirect loop', errors[0])
        self.assertIn('$.root.props.pipeline.before_render.branches[0].to',
                      errors[0])
        # Two pages that send each other away before drawing.
        self.publish(plain_page('a/'), path='a')
        self.publish(with_page_pipeline(plain_page('b/'),
                                        stage(branches=[{'to': 'page:a'}])),
                     path='b')
        errors = self.errors(with_page_pipeline(plain_page('a/'), stage(
            branches=[{'to': 'page:b', 'condition': {'auth': 'tests.pp.never'}}])))
        self.assertIn('redirect loop', ' '.join(errors))
        # After a submit, coming back to the same page is fine.
        self.assertEqual(self.errors(crud(stage(branches=[{'to': 'page:sample'}]))),
                         [])

    def test_a_list_over_a_data_source_has_no_pipeline(self):
        errors = self.errors(design(node('object_management', 'list', {
            'datasource': 'demoapp.products', 'pipeline': {'on_submit': stage()}})))
        self.assertIn('pipeline', ' '.join(errors))

    def test_only_the_page_has_before_render_and_only_forms_on_submit(self):
        document = crud()
        document['root']['children'][0]['children'][0]['children'][0]['props'][
            'pipeline'] = {'before_render': stage()}
        self.assertIn('unexpected property', ' '.join(self.errors(document)))
        page = with_page_pipeline(plain_page('p/'), stage())
        page['root']['props']['pipeline']['on_submit'] = stage()
        self.assertIn('unexpected property', ' '.join(self.errors(page)))

    def test_a_step_registered_later_makes_a_cached_page_resolve(self):
        page, errors = publishing.publish(crud(stage('tests_pp.later')), path='l',
                                          published=False)
        self.assertTrue(errors)
        register_process('tests_pp.later', check_stock, kind='validation')
        try:
            self.assertEqual(self.errors(crud(stage('tests_pp.later'))), [])
        finally:
            unregister_process('tests_pp.later')


class PPCrudClassicTests(PPTestCase):
    """``on_submit`` of the classic CRUD: its create and update pages."""

    def test_each_kind_runs_in_order(self):
        base = self.crud_page(ORDER_STEPS)
        response = self.client.post(base + 'create/', self.order(2))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(calls, ['check_stock', 'total', 'take_stock'])
        order = ShopOrder.objects.get()
        self.assertEqual(order.total, Decimal('7.00'))
        self.assertEqual(self.stock(), 3)
        # Without a branch: where the CRUD goes by default.
        self.assertEqual(response['Location'], base)

    def test_a_validation_error_saves_nothing(self):
        base = self.crud_page(ORDER_STEPS)
        response = self.client.post(base + 'create/', self.order(9))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].errors['quantity'],
                         ['Only 5 in stock'])
        self.assertEqual(calls, ['check_stock'])
        self.assertFalse(ShopOrder.objects.exists())
        self.assertEqual(self.stock(), 5)

    def test_every_validation_runs_before_stopping(self):
        base = self.crud_page(stage('tests_pp.check_stock', 'tests_pp.positive',
                                    {'name': 'tests_pp.total',
                                     'writes': ['total']}))
        response = self.client.post(base + 'create/', self.order(0))
        self.assertEqual(calls, ['check_stock', 'positive'])
        self.assertEqual(response.context['form'].non_field_errors(),
                         ['An order of nothing'])

    def test_a_failing_process_rolls_everything_back_and_is_logged(self):
        self.notebook.stock = 9999
        self.notebook.save()
        base = self.crud_page(stage('tests_pp.take_stock', 'tests_pp.explode',
                                    {'name': 'tests_pp.total',
                                     'writes': ['total']}))
        with self.assertLogs('djgentelella.designs.pipeline', logging.ERROR) as logs:
            response = self.client.post(base + 'create/', self.order(SECRET_QUANTITY))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, ['total', 'take_stock', 'explode'])
        self.assertFalse(ShopOrder.objects.exists())
        self.assertEqual(self.stock(), 9999)
        self.assertIn('nothing was saved',
                      ' '.join(response.context['form'].non_field_errors()))
        # A new object again: the form is shown to create, not to edit.
        self.assertIsNone(response.context['form'].instance.pk)
        output = '\n'.join(logs.output)
        self.assertIn('tests_pp.explode', output)
        self.assertIn('RuntimeError', output)
        self.assertNotIn(str(SECRET_QUANTITY), output)

    def test_a_process_may_refuse_with_its_own_message(self):
        base = self.crud_page(stage('tests_pp.take_stock', 'tests_pp.refuse'))
        with self.assertLogs('djgentelella.designs.pipeline', logging.WARNING) as logs:
            response = self.client.post(base + 'create/', self.order(1))
        self.assertEqual(response.context['form'].non_field_errors(),
                         ['The warehouse said no'])
        self.assertFalse(ShopOrder.objects.exists())
        self.assertEqual(self.stock(), 5)
        self.assertIn('warehouse', '\n'.join(logs.output))
        self.assertNotIn('said no', '\n'.join(logs.output))

    def test_the_branch_follows_its_condition(self):
        self.publish(plain_page('big/'), path='big')
        self.publish(plain_page('small/'), path='small')
        self.notebook.stock = 100
        self.notebook.save()
        base = self.crud_page(stage(branches=[
            {'to': 'page:big', 'condition': {'auth': 'tests.pp.big_order'}},
            {'to': 'page:small'}]))
        response = self.client.post(base + 'create/', self.order(12))
        self.assertRedirects(response, reverse('gt-design-page', args=['big']),
                             fetch_redirect_response=False)
        response = self.client.post(base + 'create/', self.order(2))
        self.assertRedirects(response, reverse('gt-design-page', args=['small']),
                             fetch_redirect_response=False)

    def test_a_branch_to_a_page_about_the_saved_object(self):
        self.publish(plain_page('order/', parent={'model': 'demoapp.ShopOrder'}),
                     path='order')
        base = self.crud_page(stage(branches=[{'to': 'page:order'}]))
        response = self.client.post(base + 'create/', self.order(1))
        order = ShopOrder.objects.get()
        self.assertEqual(response['Location'],
                         reverse('gt-design-page', args=['order/%d' % order.pk]))

    def test_a_condition_skips_a_step(self):
        base = self.crud_page(stage(
            {'name': 'tests_pp.take_stock', 'condition': {'auth': 'tests.pp.never'}}))
        self.client.post(base + 'create/', self.order(1))
        self.assertEqual(calls, [])
        self.assertEqual(ShopOrder.objects.count(), 1)
        self.assertEqual(self.stock(), 5)

    def test_the_update_page_runs_it_too(self):
        order = ShopOrder.objects.create(item=self.notebook, quantity=1)
        base = self.crud_page(ORDER_STEPS)
        response = self.client.post(base + '%d/update/' % order.pk, self.order(3))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ShopOrder.objects.get().total, Decimal('10.50'))

    def test_without_permission_no_step_runs(self):
        self.user.user_permissions.clear()
        self.grant('demoapp.view_shoporder')
        base = self.crud_page(ORDER_STEPS)
        response = self.client.post(base + 'create/', self.order(1))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(calls, [])

    def test_a_computation_cannot_touch_the_version_of_the_lock(self):
        order = ShopOrder.objects.create(item=self.notebook, quantity=1)
        with mock.patch.object(ShopOrder, 'GTLockMeta', lock_meta('quantity'),
                               create=True):
            base = self.crud_page(stage('tests_pp.touch_version'),
                                  optimistic_lock=True)
            with self.assertLogs('djgentelella.designs.pipeline', logging.ERROR):
                response = self.client.post(base + '%d/update/' % order.pk, {
                    **self.order(2), '_version': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, ['touch_version'])
        self.assertEqual(ShopOrder.objects.get().quantity, 1)

    def test_a_computation_only_sets_what_it_declares(self):
        base = self.crud_page(stage('tests_pp.touch_outside'))
        with self.assertLogs('djgentelella.designs.pipeline', logging.ERROR):
            response = self.client.post(base + 'create/', self.order(1))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ShopOrder.objects.exists())
        base = self.crud_page(stage({'name': 'tests_pp.touch_outside',
                                     'writes': ['total']}), path='orders2')
        self.assertEqual(self.client.post(base + 'create/',
                                          self.order(1)).status_code, 302)
        self.assertEqual(ShopOrder.objects.get().total, 1)


class PPObjectManagementTests(PPTestCase):
    """``on_submit`` of a table: its API."""

    def test_the_api_runs_it_and_answers_the_branch(self):
        self.publish(plain_page('done/'), path='done')
        base = self.table_page(stage(
            'tests_pp.check_stock', 'tests_pp.take_stock',
            {'name': 'tests_pp.total', 'writes': ['total']},
            branches=[{'to': 'page:done'}]))
        response = self.post_json(base, self.order(2))
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(calls, ['check_stock', 'total', 'take_stock'])
        self.assertEqual(response.json()['gtdesign_redirect'],
                         reverse('gt-design-page', args=['done']))
        self.assertEqual(ShopOrder.objects.get().total, Decimal('7.00'))
        self.assertEqual(self.stock(), 3)

    def test_errors_are_a_400(self):
        base = self.table_page(stage('tests_pp.check_stock', 'tests_pp.positive'))
        response = self.post_json(base, self.order(0))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'detail': 'An order of nothing'})
        response = self.post_json(base, self.order(8))
        self.assertEqual(response.json(), {'quantity': ['Only 5 in stock']})
        self.assertFalse(ShopOrder.objects.exists())

    def test_a_failing_process_rolls_back_the_api_save(self):
        base = self.table_page(stage('tests_pp.take_stock', 'tests_pp.explode'))
        with self.assertLogs('djgentelella.designs.pipeline', logging.ERROR):
            response = self.post_json(base, self.order(1))
        self.assertEqual(response.status_code, 400)
        self.assertIn('nothing was saved', response.json()['detail'])
        self.assertFalse(ShopOrder.objects.exists())
        self.assertEqual(self.stock(), 5)

    def test_an_update_through_the_api(self):
        order = ShopOrder.objects.create(item=self.notebook, quantity=1)
        base = self.table_page(stage({'name': 'tests_pp.total', 'writes': ['total']}))
        response = self.post_json(base + '%d/' % order.pk, self.order(4), 'put')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotIn('gtdesign_redirect', response.json())
        self.assertEqual(ShopOrder.objects.get().total, Decimal('14.00'))

    def test_the_version_is_checked_before_the_pipeline(self):
        order = ShopOrder.objects.create(item=self.notebook, quantity=1)
        base = self.table_page(ORDER_STEPS, optimistic_lock=True)
        response = self.post_json(base + '%d/' % order.pk,
                                  {**self.order(2), '_version': 'old'}, 'put')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(calls, [])

    def test_without_the_pipeline_nothing_changes(self):
        base = self.table_page()
        response = self.post_json(base, self.order(2))
        self.assertEqual(response.status_code, 201)
        self.assertNotIn('gtdesign_redirect', response.json())
        resolved, _errors = engine.resolve(table())
        self.assertIsNone(resolved.nodes['orders'].build.pipeline)


class PPBeforeRenderTests(PPTestCase):
    """``before_render`` of the page."""

    def page_url(self, path):
        return reverse('gt-design-page', args=[path])

    def test_it_adds_context(self):
        self.publish(with_page_pipeline(plain_page('hello/'), stage(
            {'name': 'tests_pp.greet', 'params': {'word': 'hola'}})), path='hello')
        response = self.client.get(self.page_url('hello'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['pipeline'], {'greeting': 'hola'})
        self.assertEqual(calls, ['greet'])

    def test_a_branch_redirects(self):
        self.publish(plain_page('login-page/'), path='login-page')
        cannot_add = {'not': {'perm': 'demoapp.add_shopitem'}}
        self.publish(with_page_pipeline(plain_page('private/'), stage(branches=[
            {'to': 'page:login-page', 'condition': cannot_add}])), path='private')
        response = self.client.get(self.page_url('private'))
        self.assertRedirects(response, self.page_url('login-page'),
                             fetch_redirect_response=False)
        self.grant('demoapp.add_shopitem')
        self.assertEqual(self.client.get(self.page_url('private')).status_code, 200)

    def test_a_step_redirects(self):
        self.publish(with_page_pipeline(plain_page('away/'),
                                        stage('tests_pp.to_login')), path='away')
        response = self.client.get(self.page_url('away'))
        self.assertEqual(response['Location'], '/accounts/login/')

    def test_a_validation_error_refuses_the_page(self):
        self.publish(with_page_pipeline(plain_page('refused/'),
                                        stage('tests_pp.positive')), path='refused')
        self.assertEqual(self.client.get(self.page_url('refused')).status_code, 403)

    def test_a_page_without_it_runs_nothing(self):
        self.publish(plain_page('quiet/'), path='quiet')
        response = self.client.get(self.page_url('quiet'))
        self.assertNotIn('pipeline', response.context)


class PPRunPipelineTests(PPTestCase):
    """The public entry point, without a component (a wizard, a view)."""

    def build(self, on_submit):
        resolved, errors = engine.resolve(crud(on_submit))
        self.assertEqual(errors, [])
        return resolved.nodes['orders'].build.pipeline

    def test_without_a_save_nor_a_pipeline(self):
        ctx = PipelineContext(None, data={'quantity': 1})
        result = run_pipeline(None, ctx)
        self.assertTrue(result.ok)
        self.assertIsNone(result.url)
        self.assertFalse(result.saved)

    def test_set_value_is_only_for_computations(self):
        ctx = PipelineContext(None, model=ShopOrder, fields=['quantity'])
        for name in ('_version', 'pk', 'id', 'total'):
            with self.assertRaises(PipelineError, msg=name):
                ctx.set_value(name, 1)
        ctx.set_value('quantity', 3)
        self.assertEqual(ctx.values, {'quantity': 3})
        with self.assertRaises(PipelineError):
            ctx.redirect('https://evil.example.com/')

    def test_the_save_is_in_the_transaction_of_the_processes(self):
        pipe = self.build(stage('tests_pp.take_stock', 'tests_pp.explode'))
        ctx = PipelineContext(None, data={'quantity': 1}, model=ShopOrder,
                              fields=['item', 'quantity'])

        def save(ctx):
            return ShopOrder.objects.create(item=self.notebook, quantity=1)

        with self.assertLogs('djgentelella.designs.pipeline', logging.ERROR):
            result = run_pipeline(pipe, ctx, save=save)
        self.assertFalse(result.ok)
        self.assertTrue(result.failed)
        self.assertFalse(result.saved)
        self.assertFalse(ShopOrder.objects.exists())
        self.assertEqual(self.stock(), 5)

    def test_factories_cache_keeps_the_pipeline(self):
        pipe = self.build(ORDER_STEPS)
        self.assertEqual([step.kind for step in pipe.steps],
                         ['validation', 'computation', 'process'])
        self.assertEqual(pipe.steps[1].writes, ('total',))
        factories.clear_cache()


@override_settings(ALLOWED_HOSTS=['*'])
class PPCodeMixinSiteTests(PPTestCase):
    """The pipeline of a view of the project is built for the Site of its
    request: a branch to a page of that Site is found."""

    def setUp(self):
        super().setUp()
        Site.objects.clear_cache()
        self.here = Site.objects.create(domain='here.example', name='Here')
        page, errors = publishing.publish(plain_page('only-here/'), site=self.here,
                                          path='only-here')
        self.assertEqual(errors, [])

    def view(self, mixin, host, **attrs):
        view = type('View', (mixin,), {'pipeline': {
            'branches': [{'to': 'page:only-here'}]}, **attrs})()
        view.request = RequestFactory().get('/', HTTP_HOST=host)
        return view

    def test_a_branch_to_a_page_of_the_site(self):
        target = reverse('gt-design-page', args=['only-here'])
        for mixin in (pipeline.PipelineFormMixin, pipeline.PipelineViewSetMixin):
            found = self.view(mixin, 'here.example').get_pipeline()
            self.assertEqual(found.branches[0].url_for(), target, mixin)
        before_render = self.view(pipeline.PipelinePageMixin, 'here.example')
        self.assertEqual(before_render.get_pipeline().branches[0].url_for(), target)

    def test_another_site_does_not_have_it(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'only-here'):
            self.view(pipeline.PipelineFormMixin, 'elsewhere.example').get_pipeline()
