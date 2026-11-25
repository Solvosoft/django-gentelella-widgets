"""djgentelella.designs: the format, the registry, the engine and the forms."""

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import Permission, User
from django.contrib.sites.models import Site
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import get_resolver

from demoapp.models import Country, ObjectManagerDemoModel, Person
from djgentelella.designs import engine, exposure, format, introspection, registry
from djgentelella.designs.builtin import HtmlComponent
from djgentelella.designs.components import ResolveContext, RuntimeComponent
from djgentelella.designs.exposure import expose, exposed_models, get_exposure
from djgentelella.designs.jsonschema import Error, validate
from djgentelella.designs.models import Page, normalize_path
from djgentelella.sites import get_current_site, site_q
from djgentelella.forms.forms import GTForm
from djgentelella.tests.designs_fixtures.components import (
    Discovered, EchoComponent, FormComponent, LoudHtml)

FIXTURES = Path(__file__).resolve().parent / 'designs_fixtures'
#: An app config stand-in whose gtdesigns module is designs_fixtures/gtdesigns.py.
FIXTURES_APP = SimpleNamespace(name='djgentelella.tests.designs_fixtures')


def load_fixture(name):
    return json.loads((FIXTURES / ('%s.json' % name)).read_text(encoding='utf-8'))


def node(type_, id_, props=None, children=None):
    item = {'type': type_, 'id': id_}
    if props is not None:
        item['props'] = props
    if children is not None:
        item['children'] = children
    return item


def html(id_, markup):
    return node('html', id_, {'html': markup})


def design(*nodes, forms=None, **meta):
    """A page with one row and one column holding ``nodes``."""
    document = {
        'schema_version': 1, 'app': 'demoapp', 'slug': 'sample', 'kind': 'page',
        'meta': {'title': 'Sample', 'url': 'sample/', 'url_name': 'sample', **meta},
        'root': node('page', 'page', children=[
            node('row', 'main', children=[
                node('col', 'body', {'width': 12}, list(nodes))])]),
    }
    if forms is not None:
        document['forms'] = forms
    return document


class DesignState:
    """Leaves the registry and the exposed models as each test found them."""

    def setUp(self):
        super().setUp()
        self._exposed = dict(exposure._EXPOSED)
        engine.clear_cache()
        # A rolled back test leaves Sites in this cache, by host and by pk.
        Site.objects.clear_cache()

    def tearDown(self):
        exposure._EXPOSED.clear()
        exposure._EXPOSED.update(self._exposed)
        exposure._state['generation'] += 1
        registry.reset()
        engine.clear_cache()
        super().tearDown()


@override_settings(LANGUAGE_CODE='en')
class JsonSchemaTests(SimpleTestCase):
    def test_errors_are_path_message_tuples(self):
        errors = validate({'a': 'x'}, {'type': 'object', 'required': ['b'],
                                       'properties': {'a': {'type': 'integer'}}})
        self.assertEqual(errors, [('$', "missing required 'b'"),
                                  ('$.a', 'expected integer, got str')])
        self.assertIsInstance(errors[0], Error)
        self.assertEqual(str(errors[1]), '$.a: expected integer, got str')

    def test_refs_lists_and_additional_properties(self):
        schema = {'$defs': {'id': {'type': 'string', 'pattern': '^[a-z]+$'}},
                  'type': 'object', 'additionalProperties': False,
                  'properties': {'ids': {'type': 'array', 'minItems': 1,
                                         'items': {'$ref': '#/$defs/id'}}}}
        self.assertEqual(validate({'ids': ['ok']}, schema), [])
        self.assertEqual([error.path for error in validate(
            {'ids': ['ok', 'NO'], 'x': 1}, schema)], ['$.ids[1]', '$.x'])

    def test_bool_is_not_a_number(self):
        self.assertEqual(len(validate(True, {'type': 'integer'})), 1)


@override_settings(LANGUAGE_CODE='en')
class FormatTests(SimpleTestCase):
    def test_envelope_of_the_editor_fixtures(self):
        for name in ('product_admin', 'sales_dashboard', 'category_products'):
            self.assertEqual(format.validate_envelope(load_fixture(name)), [], name)

    def test_envelope_errors(self):
        self.assertEqual(format.validate_envelope([]),
                         [('$', 'a design must be a JSON object')])
        document = design()
        del document['meta']['title']
        document['root']['id'] = 'Bad Id'
        paths = [error.path for error in format.validate_envelope(document)]
        self.assertIn('$.meta', paths)
        self.assertIn('$.root.id', paths)

    def test_permissions_as_object_or_list(self):
        self.assertEqual(format.validate_envelope(
            design(permissions=['demoapp.view_person'])), [])
        self.assertEqual(format.view_permissions(
            design(permissions={'view': ['demoapp.view_person']})),
            ['demoapp.view_person'])
        self.assertEqual(format.view_permissions(
            design(permissions=['demoapp.view_person'])), ['demoapp.view_person'])
        self.assertEqual(len(format.validate_envelope(
            design(permissions=['not a perm']))), 1)

    def test_upgrade_from_an_older_schema_version(self):
        """A simulated schema_version 0 kept the title at the top level."""
        def from_0(document):
            document['meta'] = {'title': document.pop('title'), 'url': 'old/',
                                'url_name': 'old'}
            return document

        old = design()
        old['schema_version'] = 0
        old['title'] = old.pop('meta')['title']
        with mock.patch.dict(format.UPGRADES, {0: from_0}):
            upgraded = format.upgrade(old)
            resolved, errors = engine.resolve(old)
        self.assertEqual(upgraded['schema_version'], format.CURRENT)
        self.assertEqual(upgraded['meta']['title'], 'Sample')
        self.assertEqual(old['schema_version'], 0, 'the argument is not changed')
        self.assertEqual(errors, [])
        self.assertEqual(resolved.title, 'Sample')

    def test_upgrade_refuses_unknown_versions(self):
        newer = dict(design(), schema_version=format.CURRENT + 1)
        with self.assertRaisesMessage(format.UpgradeError, 'newer'):
            format.upgrade(newer)
        with self.assertRaisesMessage(format.UpgradeError, 'no upgrade from'):
            format.upgrade(dict(design(), schema_version=0))
        self.assertEqual(engine.resolve(newer)[1][0].path, '$.schema_version')

    def test_hash_ignores_key_order(self):
        document = design()
        shuffled = json.loads(json.dumps(document, sort_keys=True))
        self.assertEqual(format.document_hash(document),
                         format.document_hash(shuffled))
        self.assertNotEqual(format.document_hash(document),
                            format.document_hash(design(html('x', ''))))


class RegistryTests(DesignState, SimpleTestCase):
    def test_builtins(self):
        self.assertLessEqual({'page', 'row', 'col', 'html'},
                             set(registry.get_components()))

    def test_autodiscover_imports_gtdesigns(self):
        self.assertNotIn('discovered', registry.get_components())
        registry.autodiscover([FIXTURES_APP])
        self.assertIsInstance(registry.get_component('discovered'), Discovered)
        # After a reset it is imported again and registers again.
        registry.reset()
        registry.get_components()
        registry.autodiscover([FIXTURES_APP])
        self.assertIn('discovered', registry.get_components())

    def test_apps_without_gtdesigns_are_skipped(self):
        registry.autodiscover([SimpleNamespace(name='djgentelella.blog')])

    @override_settings(GT_DESIGN_COMPONENTS=[
        'djgentelella.tests.designs_fixtures.components.EchoComponent'])
    def test_setting(self):
        registry.reset()
        self.assertIsInstance(registry.get_component('echo'), EchoComponent)

    @override_settings(GT_DESIGN_COMPONENTS=[
        'djgentelella.tests.designs_fixtures.components.LoudHtml'])
    def test_a_repeated_type_replaces_the_previous_one(self):
        registry.reset()
        self.assertIsInstance(registry.get_component('html'), LoudHtml)
        resolved, errors = engine.resolve(design(node('html', 'x', {'html': 'hi'})))
        self.assertEqual(errors, [])
        rctx = ResolveContext(resolved.document)
        self.assertIn('class="loud"', resolved.nodes['x'].component.render(
            resolved.nodes['x'].build, rctx, ''))

    def test_register_replaces_and_bumps_the_generation(self):
        before = registry.generation()
        registry.register(LoudHtml)
        self.assertGreater(registry.generation(), before)
        self.assertIsInstance(registry.get_component('html'), LoudHtml)
        registry.register(HtmlComponent)
        self.assertIs(type(registry.get_component('html')), HtmlComponent)

    def test_a_component_needs_a_type(self):
        with self.assertRaises(ValueError):
            registry.register(RuntimeComponent)


@override_settings(LANGUAGE_CODE='en')
class ExposureTests(DesignState, SimpleTestCase):
    def test_nothing_is_exposed_by_default(self):
        self.assertIsNone(get_exposure('auth.User'))

    def test_expose_as_call_and_decorator(self):
        expose(Country)
        self.assertIn('demoapp.Country', exposed_models())
        decorated = expose(fields=['name'])(Person)
        self.assertIs(decorated, Person)
        self.assertEqual(get_exposure(Person).fields, ('name',))
        self.assertIs(expose('demoapp.Country', exclude=['code']), 'demoapp.Country')
        self.assertFalse(get_exposure('demoapp.country').allows('code'))

    def test_default_and_custom_permissions(self):
        expose(Person)
        self.assertEqual(get_exposure(Person).permissions('change'),
                         ['demoapp.change_person'])
        expose(Person, perms=['demoapp.view_person'])
        self.assertEqual(get_exposure(Person).permissions('delete'),
                         ['demoapp.view_person'])
        expose(Person, perms={'view': []})
        self.assertEqual(get_exposure(Person).permissions('view'), [])
        self.assertEqual(get_exposure(Person).permissions('add'),
                         ['demoapp.add_person'])

    def test_unexposed_model_is_a_validation_error(self):
        exposure.unexpose(Person)
        rctx = ResolveContext(design())
        self.assertIsNone(rctx.model('demoapp.Person', '$.x'))
        self.assertIsNone(rctx.model('demoapp.Nope', '$.y'))
        self.assertIsNone(rctx.model('nolabel', '$.z'))
        self.assertEqual([error.path for error in rctx.errors], ['$.x', '$.y', '$.z'])
        self.assertIn('not exposed', rctx.errors[0].message)
        self.assertIn('unknown model', rctx.errors[1].message)
        expose(Person)
        self.assertIs(ResolveContext(design()).model('demoapp.Person', '$'), Person)

    def test_datasource_without_the_app(self):
        rctx = ResolveContext(design())
        with mock.patch('djgentelella.designs.components.apps.is_installed',
                        return_value=False):
            self.assertIsNone(rctx.datasource('ventas.pedidos', '$.x'))
        self.assertIn('djgentelella.datasources', rctx.errors[0].message)

    def test_datasource_with_the_app(self):
        # djgentelella.datasources is installed in the demo.
        rctx = ResolveContext(design())
        source = rctx.datasource('demoapp.person', '$.x')
        self.assertEqual(source.name, 'demoapp.person')
        self.assertIsNone(rctx.datasource('ventas.pedidos', '$.y'))
        self.assertIn("unknown data source 'ventas.pedidos'", rctx.errors[0].message)


# These tests compare messages in English: the same text whether or not
# the Spanish catalog is compiled (the demo runs in 'es').
@override_settings(LANGUAGE_CODE='en')
class EngineTests(DesignState, TestCase):
    def test_editor_fixtures_resolve(self):
        for name in ('product_admin', 'sales_dashboard', 'category_products'):
            resolved, errors = engine.resolve(load_fixture(name))
            self.assertEqual(errors, [], name)
            self.assertEqual(resolved.root.type, 'page')
            self.assertEqual(resolved.permissions, ['demoapp.view_person'])

    def test_tree_rules(self):
        cases = [
            (design(node('html', 'body', {'html': ''})), '$.root.children[0]'
             '.children[0].children[0].id', 'duplicate id'),
            (design(node('nope', 'x')), '.type', 'unknown component type'),
            (design(node('html', 'h', {'html': ''}, [node('col', 'c')])),
             '.children[0].type', "a 'col' cannot go in a 'html'"),
            (design(node('page', 'p2')), '.type', 'can only be the root'),
            (design(node('html', 'h', {'html': ''}, [html('h2', '')])),
             '.children', 'cannot have children'),
        ]
        for document, path, message in cases:
            resolved, errors = engine.resolve(document)
            self.assertIsNone(resolved)
            self.assertTrue(any(error.path.endswith(path) and message in error.message
                                for error in errors), (path, errors))
        rooted = design()
        rooted['root'] = node('row', 'page')
        self.assertIn('the root must be a page',
                      engine.resolve(rooted)[1][0].message)

    def test_col_in_row_in_col(self):
        document = design(node('row', 'inner', children=[node('col', 'c', {})]))
        self.assertEqual(engine.resolve(document)[1], [])

    def test_props_are_checked(self):
        resolved, errors = engine.resolve(design(
            node('row', 'r', children=[node('col', 'x', {'width': 13})])))
        self.assertEqual(errors[0].path, '$.root.children[0].children[0]'
                                         '.children[0].children[0].props.width')
        errors = engine.resolve(design(node('html', 'x', {})))[1]
        self.assertIn("missing required 'html'", errors[0].message)

    def test_unknown_permission(self):
        errors = engine.resolve(design(permissions=['demoapp.fly_person']))[1]
        self.assertEqual(errors, [('$.meta.permissions',
                                   "unknown permission 'demoapp.fly_person'")])

    def test_only_pages(self):
        document = dict(design(), kind='flow')
        self.assertIn('$.kind', [error.path for error in engine.resolve(document)[1]])

    def test_render_layout_and_media(self):
        registry.register(EchoComponent)
        document = design(node('echo', 'hello', {'message': '<b>hi</b>'}),
                          node('echo', 'again', {'message': 'x'}))
        document['assets'] = {'css': 'p > b { color: red } </style><script>',
                              'js': 'window.page_js = 1;'}
        resolved, errors = engine.resolve(document)
        self.assertEqual(errors, [])
        request = RequestFactory().get('/designs/sample')
        request.user = User.objects.create_user('viewer')
        content = engine.render(resolved, request).content.decode()
        self.assertIn('<title>Sample</title>', content)
        self.assertIn('left_col', content, 'the gentelella layout')
        self.assertIn('<div class="gtdesign-page" data-gtdesign="page" '
                      'data-gtdesign-page="sample">'
                      '<div class="row" data-gtdesign="main">'
                      '<div class="col-md-12" data-gtdesign="body">', content)
        self.assertIn('&lt;b&gt;hi&lt;/b&gt;', content)
        self.assertIn('<link rel="stylesheet" href="https://cdn.example.com/echo.css">',
                      content)
        self.assertEqual(content.count('/static/gentelella/js/echo.js'), 1)
        self.assertIn('<script src="/static/shared.js">', content)
        self.assertIn('window.echo_hello = true;\nwindow.echo_again = true;', content)
        self.assertIn('p > b { color: red } <\\/style><script>', content)
        self.assertNotIn('page_js', content, 'assets.js needs a trusted publisher')

    def test_resolve_page_is_cached_by_hash(self):
        page = Page.objects.create(path='cached', document=design(), is_published=True)
        with mock.patch.object(engine, 'resolve', wraps=engine.resolve) as spy:
            first = engine.resolve_page(page)
            again = engine.resolve_page(Page.objects.get(pk=page.pk))
            self.assertIs(first, again)
            self.assertEqual(spy.call_count, 1)
            page.document = design(node('html', 'x', {'html': 'new'}))
            page.save()
            self.assertIsNot(engine.resolve_page(page), first)
            self.assertEqual(spy.call_count, 2)
            expose(Country)  # what is exposed is part of the key
            engine.resolve_page(page)
            self.assertEqual(spy.call_count, 3)

    def test_cache_is_bounded(self):
        with override_settings(GT_DESIGNS_CACHE_SIZE=2):
            for index in range(4):
                page = Page(path='p%d' % index,
                            document=design(node('html', 'x', {'html': str(index)})))
                page.save()
                engine.resolve_page(page)
        self.assertEqual(len(engine._cache), 2)


@override_settings(LANGUAGE_CODE='en')
class FormsTests(DesignState, TestCase):
    def setUp(self):
        super().setUp()
        get_resolver().url_patterns  # imports the gtselects modules (lookups)
        registry.register(FormComponent)
        expose(Person)
        expose(Country)

    def resolve_form(self, data, **kwargs):
        document = design(node('test_form', 'f', {'form': 'person'}),
                          forms={'person': data}, **kwargs)
        return engine.resolve(document)

    def test_builds_a_gtform(self):
        resolved, errors = self.resolve_form({
            'model': 'demoapp.Person', 'fields': ['name', 'country', 'born_date'],
            'widgets': {'country': 'Select'},
            'help': {'name': {'title': 'Name', 'text': 'The full name.'}}})
        self.assertEqual(errors, [])
        build = resolved.forms['person']
        self.assertIs(build, resolved.nodes['f'].build.form)
        self.assertEqual(build.field_names, ['name', 'country', 'born_date'])
        form_class = build.form_class
        self.assertTrue(issubclass(form_class, GTForm))
        self.assertEqual(form_class._meta.model, Person)
        self.assertEqual(type(form_class.base_fields['born_date'].widget).__name__,
                         'DateInput')
        self.assertEqual(type(form_class.base_fields['country'].widget).__name__,
                         'Select')
        self.assertEqual(form_class.base_fields['name'].help_text, 'The full name.')
        Country.objects.create(name='Costa Rica')
        self.assertEqual(build.get_form().fields['country'].queryset.count(), 1)
        self.assertEqual(build.get_form(preview=True).fields['country']
                         .queryset.count(), 0)

    def test_autocomplete_by_default_when_there_is_a_lookup(self):
        resolved, errors = self.resolve_form({'model': 'demoapp.Person',
                                              'fields': ['country']})
        self.assertEqual(errors, [])
        field = resolved.forms['person'].fields[0]
        self.assertEqual((field.widget, field.lookup),
                         ('AutocompleteSelect', 'countrybasename'))

    def test_all_editable_fields_by_default(self):
        resolved, errors = self.resolve_form({'model': 'demoapp.Person'})
        self.assertEqual(errors, [])
        self.assertEqual(resolved.forms['person'].field_names,
                         ['name', 'num_children', 'country', 'born_date', 'last_time'])

    def test_grid(self):
        resolved, errors = self.resolve_form({
            'model': 'demoapp.Person', 'fields': ['name', 'num_children'],
            'render': 'as_grid', 'grid': [[['name'], ['num_children']]]})
        self.assertEqual(errors, [])
        self.assertEqual(resolved.forms['person'].form_class.default_render_type,
                         'as_grid')
        errors = self.resolve_form({'model': 'demoapp.Person', 'fields': ['name'],
                                    'render': 'as_grid', 'grid': [[['nope']]]})[1]
        self.assertIn('exactly once', errors[0].message)

    def test_form_errors(self):
        cases = [
            ({'model': 'demoapp.Person', 'fields': ['nope']}, 'has no field'),
            ({'model': 'demoapp.Person', 'fields': ['id']}, 'not editable'),
            ({'model': 'demoapp.Person', 'fields': ['name', 'name']}, 'twice'),
            ({'model': 'demoapp.Person', 'fields': ['name'],
              'widgets': {'name': 'DateInput'}}, 'cannot be used for a string'),
            ({'model': 'demoapp.Person', 'fields': ['country'],
              'widgets': {'country': 'TreeSelect'}}, 'tree'),
            ({'model': 'demoapp.Person', 'fields': ['name'],
              'widgets': {'born_date': 'DateInput'}}, 'not a field of this form'),
            ({'model': 'demoapp.Person', 'render': 'as_grid'}, 'needs a "grid"'),
        ]
        for data, message in cases:
            resolved, errors = self.resolve_form(data)
            self.assertIsNone(resolved)
            self.assertTrue(any(message in error.message for error in errors),
                            (message, errors))

    def test_autocomplete_needs_a_lookup(self):
        expose(ObjectManagerDemoModel)
        expose('demoapp.Community')
        resolved, errors = self.resolve_form({
            'model': 'demoapp.ObjectManagerDemoModel', 'fields': ['field_select'],
            'widgets': {'field_select': 'AutocompleteSelect'}})
        self.assertEqual(errors, [])  # communitybasename exists
        exposure.unexpose('demoapp.Community')
        errors = self.resolve_form({'model': 'demoapp.ObjectManagerDemoModel',
                                    'fields': ['field_select']})[1]
        self.assertIn('not exposed', errors[0].message)

    def test_unexposed_form_model_is_an_error_even_unused(self):
        exposure.unexpose(Person)
        document = design(forms={'unused': {'model': 'demoapp.Person'}})
        resolved, errors = engine.resolve(document)
        self.assertIsNone(resolved)
        self.assertEqual(errors[0].path, '$.forms.unused.model')
        self.assertIn('not exposed', errors[0].message)

    def test_exposure_fields_limit_the_form(self):
        expose(Person, exclude=['num_children'])
        errors = self.resolve_form({'model': 'demoapp.Person',
                                    'fields': ['num_children']})[1]
        self.assertIn('a design may use', errors[0].message)
        resolved = self.resolve_form({'model': 'demoapp.Person'})[0]
        self.assertNotIn('num_children', resolved.forms['person'].field_names)

    def test_relations_need_an_exposed_target(self):
        exposure.unexpose(Country)
        errors = self.resolve_form({'model': 'demoapp.Person',
                                    'fields': ['country']})[1]
        self.assertEqual(errors[0].path, '$.forms.person.fields')
        self.assertIn("'demoapp.Country' is not exposed", errors[0].message)

    def test_missing_form(self):
        document = design(node('test_form', 'f', {'form': 'nope'}))
        errors = engine.resolve(document)[1]
        self.assertIn("no form 'nope'", errors[0].message)

    def test_render(self):
        resolved, errors = self.resolve_form({'model': 'demoapp.Person',
                                              'fields': ['name']})
        request = RequestFactory().get('/')
        request.user = User.objects.create_user('viewer')
        content = engine.render(resolved, request).content.decode()
        self.assertIn('name="f-name"', content)


class SiteRuleTests(TestCase):
    """designs uses the Site rule (djgentelella.sites): the Site of the host, never
    SITE_ID."""

    def setUp(self):
        Site.objects.clear_cache()

    def test_contract(self):
        request = RequestFactory().get('/', HTTP_HOST='testserver')
        self.assertIsNone(get_current_site(request))
        site = Site.objects.create(domain='testserver', name='test')
        request = RequestFactory().get('/', HTTP_HOST='testserver')
        self.assertEqual(get_current_site(request), site)
        request.site = site
        self.assertEqual(get_current_site(request), site)
        self.assertEqual(str(site_q(None)), str(site_q(None, 'site')))

    def test_site_id_is_not_a_fallback(self):
        site = Site.objects.create(domain='pinned.example', name='pinned')
        with override_settings(SITE_ID=site.pk):
            self.assertIsNone(get_current_site(RequestFactory().get('/')))
            self.assertIsNone(get_current_site(None))

    def test_site_page_wins_over_global(self):
        site = Site.objects.create(domain='a.example', name='a')
        other = Site.objects.create(domain='b.example', name='b')
        global_page = Page.objects.create(path='/x/y/', document=design())
        self.assertEqual(global_page.path, 'x/y')
        own = Page.objects.create(path='x/y', document=design(), site=site)
        Page.objects.create(path='x/y', document=design(), site=other)
        self.assertEqual(Page.objects.find('x/y/', site), own)
        self.assertEqual(Page.objects.find('x/y', None), global_page)
        self.assertEqual(Page.objects.find('/x/y', Site.objects.create(
            domain='c.example', name='c')), global_page)
        self.assertIsNone(Page.objects.find('nope', site))

    def test_normalize_path(self):
        self.assertEqual(normalize_path('//a//b/'), 'a/b')

    def test_page_fields_follow_the_document(self):
        page = Page.objects.create(path='p', document=design(title='Hello'))
        self.assertEqual((page.title, page.schema_version), ('Hello', 1))
        self.assertEqual(page.hash, format.document_hash(page.document))
        self.assertEqual(str(page), 'p')


class PermissionHelpersTests(TestCase):
    def test_required_permissions(self):
        page = Page.objects.create(path='p', document=design())
        page.permissions.add(Permission.objects.get(codename='view_person'))
        self.assertEqual(page.required_permissions(), ['demoapp.view_person'])

    def test_copy_does_not_share_the_document(self):
        document = design()
        resolved = engine.resolve(copy.deepcopy(document))[0]
        self.assertEqual(resolved.document, document)


class IntrospectionTests(SimpleTestCase):
    def test_describe_model(self):
        description = introspection.describe_model(Person)
        self.assertEqual(description['label'], 'demoapp.Person')
        by_name = {item['name']: item for item in description['fields']}
        self.assertEqual(by_name['country']['relation']['to'], 'demoapp.Country')
        self.assertEqual(introspection.field_kind(by_name['born_date']), 'date')
        self.assertFalse(introspection.is_form_field(by_name['id']))
        self.assertEqual(introspection.search_field(description), 'name')
        self.assertEqual(introspection.column_type(by_name['country'], True),
                         'select2')
        self.assertEqual(introspection.filter_lookup(by_name['name']), 'icontains')
        self.assertIn('DateInput', introspection.widget_choices(by_name['born_date']))
        limited = introspection.describe_model(
            Person, fields=[Person._meta.get_field('name')])
        self.assertEqual([item['name'] for item in limited['fields']], ['name'])

    def test_choices(self):
        field = introspection.describe_field(
            ObjectManagerDemoModel._meta.get_field('radio_elements'))
        self.assertEqual(introspection.field_kind(field), 'choices')
        self.assertEqual(field['choices'][0], [1, 'A'])
