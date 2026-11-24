"""``flow_kanban`` (djgentelella.designs.flow_kanban): the objects of a flow
as cards by state, moved by running the flow's transitions."""

import json
from decimal import Decimal

from django import forms
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.db import connection
from django.test import RequestFactory, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from demoapp.models import Product, ProductCategory
from djgentelella.designs import engine, flow_kanban, publishing, registry
from djgentelella.designs.exposure import expose, unexpose
from djgentelella.designs.models import Page
from djgentelella.flows import base
from djgentelella.flows.base import Flow, Transition, flow_for_instance, register_flow
from djgentelella.flows.exceptions import TransitionBlocked
from djgentelella.flows.models import FlowInstance, FlowTransitionLog
from djgentelella.models import MenuItem
from djgentelella.tests.DesignsPages_Test import DesignClient, grant
from djgentelella.tests.Designs_Test import design, node

FLOW = 'tests.kanban'


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['description']

    def clean_description(self):
        text = self.cleaned_data['description']
        if len(text) < 5:
            raise forms.ValidationError('Write at least five characters.')
        return text


def has_a_price(context):
    if context.obj.price <= 0:
        raise TransitionBlocked('It needs a price first.')
    return True


class KanbanFlow(Flow):
    name = FLOW
    model = Product
    states = [('todo', 'To do'), ('doing', 'Doing'), ('review', 'In review'),
              ('done', 'Done'), ('archived', 'Archived')]
    initial = 'todo'
    transitions = [
        Transition('start', 'todo', 'doing', label='Start',
                   perms=['demoapp.change_product']),
        Transition('finish', 'doing', 'done', label='Finish',
                   perms=['demoapp.change_product']),
        Transition('ship', 'doing', 'done', label='Ship',
                   perms=['demoapp.change_product']),
        Transition('send', 'doing', 'review', label='Send to review',
                   perms=['demoapp.change_product'], form=ReviewForm),
        Transition('approve', 'review', 'done', label='Approve',
                   perms=['demoapp.change_product'], condition=has_a_price),
        Transition('archive', 'done', 'archived', label='Archive',
                   perms=['demoapp.delete_product']),
        Transition('auto_close', 'archived', 'todo', auto=True,
                   condition=lambda context: False),
    ]


class MenuFlow(Flow):
    name = 'tests.kanban.menu'
    model = MenuItem
    states = [('new', 'New'), ('seen', 'Seen')]
    initial = 'new'
    transitions = [Transition('see', 'new', 'seen', label='See',
                              perms=['djgentelella.change_menuitem'])]


register_flow(KanbanFlow)
register_flow(MenuFlow)


def kanban(**props):
    return design(node('flow_kanban', 'board', {'flow': FLOW, **props}))


class KanbanBase(DesignClient):
    def setUp(self):
        super().setUp()
        # Loading the registry imports the gtdesigns modules, which expose
        # the demo's models again: first, so the tests' exposures stay.
        registry.get_components()
        expose(Product)
        expose(MenuItem)
        self.user = grant(self.user, 'demoapp.view_product', 'demoapp.change_product')
        self.client.force_login(self.user)

    def product(self, name, state=None, price='10.00', **kwargs):
        obj = Product.objects.create(name=name, price=Decimal(price), **kwargs)
        if state is not None:
            flow = KanbanFlow()
            flow.start(obj)
            FlowInstance.objects.filter(flow=FLOW, object_id=str(obj.pk)).update(
                state=state, tokens=[{'id': 1, 'activity': state, 'status': 'active',
                                      'scope': []}], token_seq=1)
        return obj

    def page(self, **props):
        return self.publish(kanban(**props))

    def url(self, page, rest=''):
        return reverse('gt-design-endpoint', kwargs={
            'page_id': page.pk, 'node_id': 'board', 'rest': rest})

    def state(self, obj):
        instance = FlowInstance.objects.filter(flow=FLOW, object_id=str(obj.pk)).first()
        return instance.state if instance else 'todo'

    def board(self):
        response = self.get('sample')
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def config(self, content):
        start = content.index('<script id="board_gtconfig" type="application/json">')
        start = content.index('>', start) + 1
        return json.loads(content[start:content.index('</script>', start)])


# These tests compare messages in English: the same text whether or not
# the Spanish catalog is compiled (the demo runs in 'es').
@override_settings(LANGUAGE_CODE='en')
class SchemaTests(KanbanBase):
    def errors(self, **props):
        return [tuple(error) for error in engine.resolve(kanban(**props))[1]]

    def test_a_valid_board(self):
        self.assertEqual(self.errors(states=['todo', 'doing'], fields=['price'],
                                     title_field='name', ordering=['name'],
                                     limit=3, page_size=5), [])

    def test_an_unknown_flow(self):
        self.assertEqual(self.errors(flow='tests.nope'), [
            ('$.root.children[0].children[0].children[0].props.flow',
             "no flow 'tests.nope' (djgentelella.flows)")])

    def test_an_unknown_state(self):
        self.assertEqual(self.errors(states=['todo', 'limbo']), [
            ('$.root.children[0].children[0].children[0].props.states[1]',
             "flow 'tests.kanban' has no state 'limbo'")])

    def test_a_repeated_state(self):
        errors = self.errors(states=['todo', 'todo'])
        self.assertEqual(errors[0][1], "state 'todo' is repeated")

    def test_the_props_shape(self):
        errors = self.errors(limit=0, page_size=500, color='red')
        messages = sorted(message for _path, message in errors)
        self.assertEqual(len(messages), 3, messages)

    def test_fields_must_be_exposed_and_shown(self):
        expose(Product, fields=['name', 'price', 'tags'])
        errors = self.errors(fields=['status', 'tags'])
        self.assertEqual([message for _path, message in errors], [
            "'status' is not a field of demoapp.Product the design may show",
            "'tags' cannot be shown on a card"])

    def test_the_model_must_be_exposed(self):
        unexpose(Product)
        errors = self.errors()
        self.assertIn('is not exposed to designs', errors[0][1])

    def test_ordering_and_site_field(self):
        errors = self.errors(ordering=['-nope'], site_field='category')
        self.assertEqual([message for _path, message in errors], [
            "unknown field '-nope'",
            "'category' is not a foreign key of demoapp.Product to sites.Site"])

    def test_publish_refuses_a_broken_board(self):
        page, errors = publishing.publish(kanban(states=['nope']), path='x')
        self.assertIsNone(page)
        self.assertTrue(errors)

    def test_the_preview_reads_no_row(self):
        self.product('Real', 'doing')
        resolved, errors = engine.resolve(kanban(fields=['price'],
                                                 states=['todo', 'doing']),
                                          preview=True)
        self.assertEqual(errors, [])
        node = resolved.nodes['board']
        with self.assertNumQueries(0):
            html = node.component.render(node.build, engine.make_context(
                resolved.document, preview=True), '')
        self.assertIn('Doing', html)
        self.assertIn('Product 2', html)
        self.assertNotIn('Real', html)
        self.assertNotIn('gtconfig', html)

    def test_default_states_skip_the_transient_activities(self):
        resolved, errors = engine.resolve(kanban())
        self.assertEqual(errors, [])
        self.assertEqual(resolved.nodes['board'].build.states,
                         ['todo', 'doing', 'review', 'done', 'archived'])


@override_settings(LANGUAGE_CODE='en')
class BoardTests(KanbanBase):
    def test_cards_by_state(self):
        self.page(fields=['price', 'status'])
        self.product('Alpha')
        self.product('Beta', 'doing')
        self.product('Gamma', 'done', status='active')
        content = self.board()
        self.assertIn('data-state="todo"', content)
        config = self.config(content)
        self.assertEqual(config['states'], ['todo', 'doing', 'review', 'done',
                                            'archived'])
        # The columns the user may move each card to (perms of the flow).
        self.assertEqual(config['moves'], {
            'todo': ['doing'], 'doing': ['review', 'done'], 'review': ['done'],
            'done': [], 'archived': []})
        for name in ('Alpha', 'Beta', 'Gamma'):
            self.assertIn(name, content)
        self.assertIn('Active', content)  # the choice's label
        self.assertIn('Move to', content)

    def test_only_what_get_queryset_allows(self):
        self.page()
        self.product('Secret', 'doing')
        other = User.objects.create_user('beto', password='pw')
        self.client.force_login(other)
        # Without view_product, get_queryset keeps only the states the user
        # can act on: none.
        self.assertNotIn('Secret', self.board())
        grant(other, 'demoapp.change_product')
        self.assertIn('Secret', self.board())

    def test_get_queryset_is_the_rule(self):
        class Narrow(KanbanFlow):
            def get_queryset(self, user):
                return super().get_queryset(user).exclude(name='Hidden')
        original = Narrow()
        versions = base._registry[FLOW]
        saved = versions[1]
        versions[1] = original
        try:
            page = self.page()
            hidden = self.product('Hidden', 'doing')
            self.product('Shown', 'doing')
            content = self.board()
            self.assertIn('Shown', content)
            self.assertNotIn('Hidden', content)
            response = self.client.get(self.url(page, '%d/transitions/' % hidden.pk),
                                       {'target': 'done'})
            self.assertEqual(response.status_code, 404)
        finally:
            versions[1] = saved

    def test_only_the_current_site(self):
        page = self.page()
        here = Site.objects.create(domain='testserver', name='here')
        there = Site.objects.create(domain='there.example', name='there')
        mine = self.product('Mine', 'doing')
        other = self.product('Theirs', 'doing')
        self.product('Global', 'doing')
        FlowInstance.objects.filter(object_id=str(mine.pk)).update(site=here)
        FlowInstance.objects.filter(object_id=str(other.pk)).update(site=there)
        content = self.board()
        self.assertIn('Mine', content)
        self.assertIn('Global', content)
        self.assertNotIn('Theirs', content)
        response = self.client.get(self.url(page, '%d/transitions/' % other.pk),
                                   {'target': 'done'})
        self.assertEqual(response.status_code, 404)

    def test_the_site_field(self):
        here = Site.objects.create(domain='testserver', name='here')
        there = Site.objects.create(domain='there.example', name='there')
        self.user = grant(self.user, 'djgentelella.view_menuitem')
        self.client.force_login(self.user)
        for title, site in (('Here item', here), ('There item', there),
                            ('Global item', None)):
            MenuItem.objects.create(title=title, url_name='/', site=site)
        self.publish(design(node('flow_kanban', 'board', {
            'flow': 'tests.kanban.menu', 'site_field': 'site'})))
        content = self.board()
        self.assertIn('Here item', content)
        self.assertIn('Global item', content)
        self.assertNotIn('There item', content)

    def test_anonymous_and_no_flow(self):
        page = self.page()
        self.client.logout()
        self.assertEqual(self.get('sample').status_code, 302)
        self.assertEqual(self.client.get(self.url(page, 'cards/'),
                                         {'state': 'todo'}).status_code, 403)

    def test_limit_marks_the_column(self):
        self.page(limit=1)
        self.product('One', 'doing')
        self.product('Two', 'doing')
        content = self.board()
        self.assertIn('gtkanban-column gtkanban-over" data-state="doing"', content)
        self.assertIn('2</span> / 1', content)

    def test_load_more(self):
        page = self.page(page_size=2, ordering=['name'])
        for name in ('a1', 'a2', 'a3', 'a4', 'a5'):
            self.product(name, 'doing')
        content = self.board()
        self.assertIn('a1', content)
        self.assertNotIn('a3', content)
        response = self.client.get(self.url(page, 'cards/'),
                                   {'state': 'doing', 'offset': 2})
        data = response.json()
        self.assertEqual((data['count'], data['has_more']), (2, True))
        self.assertIn('a3', data['html'])
        self.assertIn('a4', data['html'])
        data = self.client.get(self.url(page, 'cards/'),
                               {'state': 'doing', 'offset': 4}).json()
        self.assertEqual((data['count'], data['has_more']), (1, False))
        self.assertEqual(self.client.get(self.url(page, 'cards/'),
                                         {'state': 'limbo'}).status_code, 404)

    def queries(self, cards):
        self.page(fields=['price', 'category'])
        category = ProductCategory.objects.create(name='Food')
        for index in range(cards):
            self.product('P%d' % index, ['todo', 'doing', 'done'][index % 3],
                         category=category)
        self.board()  # the caches: page, flow, permissions of the session
        with CaptureQueriesContext(connection) as captured:
            content = self.board()
        self.assertEqual(content.count(' data-pk="'), cards)
        return len(captured)

    def test_the_board_takes_two_queries(self):
        resolved, _errors = engine.resolve(kanban(fields=['price', 'category']))
        build = resolved.nodes['board'].build
        category = ProductCategory.objects.create(name='Tools')
        for index in range(12):
            self.product('Q%d' % index, ['todo', 'doing'][index % 2],
                         category=category)
        request = RequestFactory().get('/')
        request.user, request.site = self.user, None
        flow = flow_kanban.kanban_flow(build, request)
        flow.get_queryset(self.user)  # the user's permissions, cached
        # The counts per state and the first page of every column.
        with self.assertNumQueries(2):
            columns, _moves = flow_kanban.board(flow, build, request)
        self.assertEqual([column['total'] for column in columns], [6, 6, 0, 0, 0])
        self.assertEqual(str(columns[0]['cards'][0]['fields'][1][1]), 'Tools')

    def test_queries_do_not_grow_with_the_cards(self):
        one = self.queries(1)
        Product.objects.all().delete()
        FlowInstance.objects.all().delete()
        many = self.queries(30)
        self.assertEqual(one, many)


@override_settings(LANGUAGE_CODE='en')
class MoveTests(KanbanBase):
    def setUp(self):
        super().setUp()
        self.board_page = self.page(fields=['price'])

    def options(self, obj, target):
        response = self.client.get(
            self.url(self.board_page, '%s/transitions/' % obj.pk), {'target': target})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def move(self, obj, transition, **data):
        return self.client.post(self.url(self.board_page, '%s/move/' % obj.pk),
                                {'transition': transition, **data})

    def test_one_transition(self):
        obj = self.product('Alpha')
        data = self.options(obj, 'doing')
        self.assertEqual([item['name'] for item in data['transitions']], ['start'])
        response = self.move(obj, 'start', **{'flow_comment-comment': 'go'})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual((body['state'], body['state_label']), ('doing', 'Doing'))
        self.assertIn('data-state="doing"', body['card'])
        self.assertEqual(self.state(obj), 'doing')
        log = FlowTransitionLog.objects.get(transition='start')
        self.assertEqual((log.source, log.target, log.user, log.comment, log.kind),
                         ('todo', 'doing', self.user, 'go', 'transition'))
        # The card is in its new column after a reload.
        self.assertIn('data-pk="%d" data-state="doing"' % obj.pk, self.board())

    def test_several_transitions(self):
        obj = self.product('Beta', 'doing')
        data = self.options(obj, 'done')
        self.assertEqual([item['name'] for item in data['transitions']],
                         ['finish', 'ship'])
        self.assertEqual(self.move(obj, 'ship').status_code, 200)
        self.assertEqual(FlowTransitionLog.objects.get(
            instance__object_id=str(obj.pk), kind='transition').transition, 'ship')

    def test_no_transition(self):
        obj = self.product('Gamma')
        data = self.options(obj, 'review')
        self.assertEqual(data['transitions'], [])
        self.assertEqual(data['detail'], 'No transition goes from To do to In review.')
        self.assertEqual(self.move(obj, 'send').status_code, 403)
        self.assertEqual(self.state(obj), 'todo')

    def test_without_permission(self):
        obj = self.product('Delta', 'done')
        data = self.options(obj, 'archived')
        self.assertEqual(data['transitions'], [])
        self.assertEqual(data['detail'], 'You cannot run Archive.')
        response = self.move(obj, 'archive')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['detail'], 'You cannot run Archive.')
        self.assertEqual(self.state(obj), 'done')
        self.assertFalse(FlowTransitionLog.objects.filter(transition='archive'))

    def test_a_false_condition(self):
        obj = self.product('Epsilon', 'review', price='0')
        data = self.options(obj, 'done')
        self.assertEqual(data['transitions'], [])
        self.assertEqual(data['refused'], [{'name': 'approve', 'label': 'Approve',
                                            'reason': 'It needs a price first.'}])
        response = self.move(obj, 'approve')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['detail'], 'It needs a price first.')
        self.assertEqual(self.state(obj), 'review')

    def test_the_condition_is_checked_again_when_it_runs(self):
        obj = self.product('Zeta', 'review')
        self.assertEqual(len(self.options(obj, 'done')['transitions']), 1)
        Product.objects.filter(pk=obj.pk).update(price=0)  # meanwhile
        self.assertEqual(self.move(obj, 'approve').status_code, 403)
        self.assertEqual(self.state(obj), 'review')

    def test_a_form_valid_and_invalid(self):
        obj = self.product('Eta', 'doing')
        data = self.options(obj, 'review')
        self.assertEqual(data['transitions'], [{
            'name': 'send', 'label': 'Send to review', 'form': True,
            'css_class': 'btn-primary'}])
        response = self.client.get(self.url(self.board_page, '%s/form/' % obj.pk),
                                   {'transition': 'send'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('name="flow-description"', response.json()['html'])
        self.assertIn('name="transition" value="send"', response.json()['html'])
        response = self.move(obj, 'send', **{'flow-description': 'no'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['errors'], {
            'description': ['Write at least five characters.']})
        self.assertIn('Write at least five characters.', response.json()['html'])
        self.assertEqual(self.state(obj), 'doing')
        response = self.move(obj, 'send', **{'flow-description': 'Looks good'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.state(obj), 'review')
        obj.refresh_from_db()
        self.assertEqual(obj.description, 'Looks good')
        log = FlowTransitionLog.objects.get(transition='send')
        self.assertEqual(log.data, {'description': 'Looks good'})

    def test_the_form_of_a_refused_transition(self):
        obj = self.product('Theta')
        response = self.client.get(self.url(self.board_page, '%s/form/' % obj.pk),
                                   {'transition': 'send'})
        self.assertEqual(response.status_code, 403)

    def test_unknown_and_automatic_transitions(self):
        obj = self.product('Iota')
        self.assertEqual(self.move(obj, 'nope').status_code, 404)
        self.assertEqual(self.move(obj, 'auto_close').status_code, 404)
        self.assertEqual(self.client.get(
            self.url(self.board_page, '%s/transitions/' % obj.pk),
            {'target': 'limbo'}).status_code, 404)
        self.assertEqual(self.client.get(
            self.url(self.board_page, 'abc/transitions/'),
            {'target': 'doing'}).status_code, 404)

    def test_a_transition_to_a_hidden_column(self):
        page = self.publish(kanban(states=['todo', 'doing']), path='small')
        obj = self.product('Kappa', 'doing')
        response = self.client.post(self.url(page, '%s/move/' % obj.pk),
                                    {'transition': 'finish'})
        self.assertEqual(response.status_code, 404)

    def test_csrf_is_checked(self):
        obj = self.product('Lambda')
        self.client.logout()
        client = self.client_class(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(self.url(self.board_page, '%s/move/' % obj.pk),
                               {'transition': 'start'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.state(obj), 'todo')

    def test_it_runs_through_the_flow(self):
        """Nothing changes the state but Flow.run (and its _step): the run is
        refused, and nothing changes, when the engine refuses it."""
        obj = self.product('Mu', 'doing')
        flow = flow_for_instance(FlowInstance.objects.get(object_id=str(obj.pk)))
        flow.suspend(obj)
        data = self.options(obj, 'done')
        self.assertEqual(data['transitions'], [])
        self.assertIn('suspended', data['detail'])
        self.assertEqual(self.move(obj, 'finish').status_code, 403)
        self.assertEqual(self.state(obj), 'doing')
        self.assertIn('Suspended', self.board())

    def test_a_page_of_another_site_is_not_served(self):
        there = Site.objects.create(domain='there.example', name='there')
        Page.objects.filter(pk=self.board_page.pk).update(site=there)
        obj = self.product('Nu')
        self.assertEqual(self.move(obj, 'start').status_code, 404)
