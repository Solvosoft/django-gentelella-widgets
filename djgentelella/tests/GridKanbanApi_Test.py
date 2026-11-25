"""W21: the grid and the Kanban as public API for code generated from a
design (djgentelella-editor) and for application builders (djodo).

The page context of each one is built from a build alone, without a
published :class:`~djgentelella.designs.models.Page`; ``FlowKanbanViewSet``
serves the build of :meth:`get_build`; and a :class:`ResolveContext` can
answer the flows a design names (``flow``), to validate a board over a flow
that is not published yet.
"""

import dataclasses

from django import forms
from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from demoapp.models import Product
from djgentelella.designs import engine, flow_kanban, grid
from djgentelella.designs.components import ResolveContext
from djgentelella.designs.data_components import find_flow
from djgentelella.flows.base import Flow, Transition
from djgentelella.tests.Designs_Test import design, node
from djgentelella.tests.DesignsData_Test import (
    ALL_PRODUCT_PERMS, DataDesignTestCase, product_form,
)
from djgentelella.tests.DesignsHooks_Test import gtconfig
from djgentelella.tests.FlowKanban_Test import FLOW, KanbanBase, kanban
from djgentelella.tests.InteractiveGrid_Test import COLUMNS, grid_node

__all__ = ['PublicNamesTests', 'GridPageContextTests', 'KanbanPageContextTests',
           'KanbanGetBuildTests', 'FlowHookTests']

FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']


def config_of(html, node_id):
    return gtconfig(str(html), node_id)


class PublicNamesTests(TestCase):
    def test_the_names_generated_code_uses_are_public(self):
        for name in ('GridState', 'NOT_SHOWN', 'NOT_EDITABLE', 'required_fields',
                     'grid_page_context', 'grid_config', 'grid_columns',
                     'grid_viewset_for', 'TEMPLATE'):
            self.assertIn(name, grid.__all__)
            self.assertTrue(hasattr(grid, name), name)
        for name in ('board', 'render_cards', 'resting_states', 'kanban_flow',
                     'kanban_page_context', 'kanban_config', 'kanban_messages',
                     'FlowKanbanViewSet', 'TEMPLATE'):
            self.assertIn(name, flow_kanban.__all__)
            self.assertTrue(hasattr(flow_kanban, name), name)


@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS)
class GridPageContextTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        self.grant(*ALL_PRODUCT_PERMS)
        resolved, errors = engine.resolve(design(grid_node()))
        self.assertEqual(errors, [])
        self.build = resolved.nodes['grid'].build
        self.request = RequestFactory().get('/somewhere/')
        self.request.user = self.user

    def test_without_a_page_the_same_context_as_the_page(self):
        page = self.publish(design(grid_node()), path='grid')
        on_page = gtconfig(self.client.get('/designs/grid').content.decode(), 'grid')
        context = grid.grid_page_context(self.build, self.request, '/my/grid/')
        self.assertEqual(set(context), {'b', 'cells', 'allowed', 'config'})
        self.assertIs(context['b'], self.build)
        config = config_of(context['config'], 'grid')
        self.assertEqual(config['url'], '/my/grid/')
        self.assertEqual(on_page['url'], self.api(page, 'grid'))
        self.assertEqual({**config, 'url': None}, {**on_page, 'url': None})
        self.assertEqual([name for name, _field in context['cells']], COLUMNS)
        self.assertEqual(context['allowed'],
                         {'create': True, 'update': True, 'destroy': True})

    def test_none_when_the_request_may_not_see_it(self):
        self.user.user_permissions.clear()
        self.request.user = User.objects.get(pk=self.user.pk)
        self.assertIsNone(grid.grid_page_context(self.build, self.request, '/g/'))
        self.request.user = AnonymousUser()
        self.assertIsNone(grid.grid_page_context(self.build, self.request, '/g/'))
        self.request.user = self.user
        self.assertIsNone(grid.grid_page_context(self.build, self.request, None))

    def test_a_generated_build_with_its_own_form_and_columns(self):
        class GeneratedForm(forms.ModelForm):
            class Meta:
                model = Product
                fields = ['name', 'price']

        build = dataclasses.replace(self.build, form=None, editable=['name', 'price'])
        columns = [{'name': name, 'title': name.title(), 'kind': 'text'}
                   for name in COLUMNS]
        context = grid.grid_page_context(build, self.request, '/gen/',
                                         form_class=GeneratedForm, columns=columns)
        config = config_of(context['config'], 'grid')
        self.assertEqual([(column['name'], column['editable'])
                          for column in config['columns']],
                         [('name', True), ('price', True), ('status', False),
                          ('category', False)])
        self.assertEqual([name for name, _field in context['cells']], ['name', 'price'])
        self.assertIn('name="grid-__row__-price"', str(context['cells'][1][1]))

    def test_columns_hidden_by_a_condition_are_left_out(self):
        self.user.user_permissions.clear()
        self.grant('demoapp.view_product', 'demoapp.change_product')
        resolved, _errors = engine.resolve(design(grid_node(
            column_conditions={'category': {'perm': 'demoapp.delete_product'}})))
        self.request.user = self.user
        context = grid.grid_page_context(resolved.nodes['grid'].build, self.request,
                                         '/g/')
        config = config_of(context['config'], 'grid')
        self.assertEqual([column['name'] for column in config['columns']],
                         ['name', 'price', 'status'])
        self.assertEqual(config['allowed'],
                         {'create': False, 'update': True, 'destroy': False})


@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS)
class KanbanPageContextTests(KanbanBase):
    def setUp(self):
        super().setUp()
        self.todo = self.product('Todo', 'todo')
        self.doing = self.product('Doing', 'doing')
        resolved, errors = engine.resolve(kanban())
        self.assertEqual(errors, [])
        self.build = resolved.nodes['board'].build
        self.request = RequestFactory().get('/board/')
        self.request.user = self.user

    def test_without_a_page_the_same_context_as_the_page(self):
        page = self.page()
        on_page = gtconfig(self.get('sample').content.decode(), 'board')
        context = flow_kanban.kanban_page_context(self.build, self.request, '/k/')
        self.assertEqual(set(context), {'b', 'columns', 'config'})
        config = config_of(context['config'], 'board')
        self.assertEqual(config['urls'], {'base': '/k/'})
        self.assertEqual(on_page['urls'], {'base': self.url(page)})
        self.assertEqual({**config, 'urls': None}, {**on_page, 'urls': None})
        self.assertEqual(config['messages'], flow_kanban.kanban_messages())
        by_state = {column['state']: column for column in context['columns']}
        self.assertIn('data-pk="%d"' % self.todo.pk, by_state['todo']['html'])
        self.assertIn('data-pk="%d"' % self.doing.pk, by_state['doing']['html'])

    def test_none_when_the_request_may_not_see_it(self):
        self.request.user = AnonymousUser()
        self.assertIsNone(flow_kanban.kanban_page_context(self.build, self.request,
                                                          '/k/'))
        self.request.user = self.user
        self.assertIsNone(flow_kanban.kanban_page_context(self.build, self.request, ''))
        missing = dataclasses.replace(self.build, flow='tests.no_such_flow')
        self.assertIsNone(flow_kanban.kanban_page_context(missing, self.request, '/k/'))
        extra = dataclasses.replace(self.build, states=self.build.states + ['nowhere'])
        self.assertIsNone(flow_kanban.kanban_page_context(extra, self.request, '/k/'))


class GeneratedBoard(flow_kanban.FlowKanbanViewSet):
    """What djgentelella-editor generates: the build as a class attribute."""


@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS)
class KanbanGetBuildTests(KanbanBase):
    def setUp(self):
        super().setUp()
        self.product('Todo', 'todo')
        resolved, _errors = engine.resolve(kanban())
        self.build = resolved.nodes['board'].build

    def call(self, viewset, request_build=None):
        request = APIRequestFactory().get('/board/')
        if request_build is not None:
            request.gtdesign_build = request_build
        force_authenticate(request, user=self.user)
        return viewset.as_view({'get': 'list'})(request)

    def test_the_build_of_the_class(self):
        viewset = type('Board', (GeneratedBoard,), {'kanban_build': self.build})
        response = self.call(viewset)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'states': self.build.states})

    def test_by_default_the_build_of_the_request(self):
        response = self.call(flow_kanban.FlowKanbanViewSet, self.build)
        self.assertEqual(response.data, {'states': self.build.states})
        self.assertEqual(self.call(flow_kanban.FlowKanbanViewSet).status_code, 404)

    def test_the_class_build_wins_over_the_request(self):
        other = dataclasses.replace(self.build, states=['todo'])
        viewset = type('Board', (GeneratedBoard,), {'kanban_build': other})
        self.assertEqual(self.call(viewset, self.build).data, {'states': ['todo']})

    def test_the_page_endpoint_still_serves_its_build(self):
        page = self.page()
        response = self.client.get(self.url(page))
        self.assertEqual(response.json(), {'states': self.build.states})


class DraftFlow(Flow):
    """A flow the editor designs and has not generated nor published: never
    registered."""

    name = 'demoapp.w21_draft'
    model = Product
    states = [('new', 'New'), ('open', 'Open'), ('closed', 'Closed')]
    initial = 'new'
    transitions = [Transition('open', 'new', 'open', label='Open'),
                   Transition('close', 'open', 'closed', label='Close')]


class EditorContext(ResolveContext):
    """Answers the flows of the app being designed, then djgentelella's."""

    drafts = {DraftFlow.name: DraftFlow()}

    def flow(self, name, path=None):
        found = self.drafts.get(name) or self.drafts.get(
            '%s.%s' % (self.design.get('app'), name))
        return found if found is not None else super().flow(name, path)


@override_settings(LANGUAGE_CODE='en')
class FlowHookTests(TestCase):
    def board(self, flow):
        return design(node('flow_kanban', 'board', {'flow': flow}))

    def test_a_board_over_a_flow_that_is_not_published(self):
        resolved, errors = engine.resolve(self.board('w21_draft'),
                                          context=EditorContext)
        self.assertEqual(errors, [])
        build = resolved.nodes['board'].build
        self.assertEqual(build.flow, 'demoapp.w21_draft')
        self.assertEqual(build.states, ['new', 'open', 'closed'])
        self.assertEqual(build.model, Product)

    def test_without_the_hook_it_is_an_error(self):
        _resolved, errors = engine.resolve(self.board('demoapp.w21_draft'))
        self.assertEqual([(error.path, error.message) for error in errors],
                         [('$.root.children[0].children[0].children[0].props.flow',
                           "no flow 'demoapp.w21_draft' (djgentelella.flows)")])

    def test_the_hook_falls_back_to_the_registered_flows(self):
        resolved, errors = engine.resolve(self.board(FLOW), context=EditorContext)
        self.assertEqual(errors, [])
        self.assertEqual(resolved.nodes['board'].build.flow, FLOW)

    def test_row_links_ask_the_hook_too(self):
        document = design(node('object_management', 'products', {
            'model': 'demoapp.Product', 'form': 'product_form', 'row_links': [
                {'title': 'Open', 'url_name': 'flow:demoapp.w21_draft'}]}),
            forms=product_form())
        _resolved, errors = engine.resolve(document)
        self.assertTrue(any('w21_draft' in error.message for error in errors))
        _resolved, errors = engine.resolve(document, context=EditorContext)
        self.assertEqual(errors, [])

    def test_find_flow_is_the_hook(self):
        context = EditorContext(self.board('x'))
        self.assertIsInstance(find_flow(context, 'demoapp.w21_draft'), DraftFlow)
        plain = ResolveContext(self.board('x'))
        self.assertIsNone(plain.flow('demoapp.w21_draft'))
        self.assertEqual(plain.errors, [])
        self.assertIsNone(plain.flow('demoapp.w21_draft', '$.here'))
        self.assertEqual([error.path for error in plain.errors], ['$.here'])
