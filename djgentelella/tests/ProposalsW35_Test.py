"""The last proposals of the roadmap that W35 adds as API.

D20: reviewers of the feedback per Site, public views marked as such, the
PWA under the script prefix, the login page with blocks, the user menu with
entries a project registers and ``#rgb`` colours in a theme. D21: a public
registry of widgets, tags on the pipeline steps, a stable key of the rows of a
data source and a text area with buttons under it. E15: the master-detail of
a design page read by the engine.
"""

import json
import re

from django import forms
from django.contrib.auth.models import AnonymousUser
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.template import engines
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import resolve, reverse, set_script_prefix
from django.views import View

from demoapp.models import Product
from djgentelella.datasources.base import (
    ROW_KEY_MAX_LENGTH, Column, FunctionDataSource, ModelDataSource, restricted,
)
from djgentelella.designs import engine, pipeline
from djgentelella.designs.data_components import master_detail_of
from djgentelella.designs.models import Page
from djgentelella.feedback.conf import can_answer_feedback, is_feedback_reviewer
from djgentelella.forms import widgetmap
from djgentelella.menu import get_menu_widget
from djgentelella.menu_widgets.user import (
    UserMenu, register_user_menu_entry, registered_user_menu_entries,
    unregister_user_menu_entry, user_menu_entries,
)
from djgentelella.models import Feedback, MenuItem, SiteTheme
from djgentelella.public import is_public_view, public_view
from djgentelella.pwa.manifest import build_manifest, worker_config
from djgentelella.tests.Designs_Test import design, node
from djgentelella.tests.DesignsData_Test import DataDesignTestCase
from djgentelella.tests.ThemeDiagramFeedback_Test import FAST_HASHERS, make_user
from djgentelella.theme import values
from djgentelella.theme.forms import SiteThemeForm
from djgentelella.widgets.core import Textarea, WidgetAction


# -- D20 1: reviewers of the feedback per Site -----------------------------------------

def site_reviewers(request, user):
    """The reviewers of a.example: the users whose name starts with ``a-``."""
    return request.get_host() == 'a.example' and user.username.startswith('a-')


def nobody_answers(request, user):
    return False


@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS,
                   ALLOWED_HOSTS=['*'], GT_FEEDBACK=True)
class FeedbackReviewerTests(TestCase):
    def setUp(self):
        cache.clear()
        Site.objects.clear_cache()
        self.site_a = Site.objects.create(domain='a.example', name='A')
        self.site_b = Site.objects.create(domain='b.example', name='B')
        self.author = make_user('author')
        self.local = make_user('a-rita')
        self.global_reviewer = make_user('global', 'djgentelella.view_feedback',
                                         'djgentelella.change_feedback')
        self.feedback = Feedback.objects.create(user=self.author, site=self.site_a,
                                                text='A one')
        Feedback.objects.create(user=self.author, site=self.site_b, text='B one')
        self.inbox = reverse('gt_feedback_inbox')
        self.detail = reverse('gt_feedback_detail', args=[self.feedback.pk])

    def request(self, user, host='a.example'):
        request = RequestFactory().get('/', HTTP_HOST=host)
        request.user = user
        return request

    def test_the_global_permissions_without_the_hook(self):
        self.assertTrue(is_feedback_reviewer(self.request(self.global_reviewer)))
        self.assertTrue(can_answer_feedback(self.request(self.global_reviewer)))
        self.assertFalse(is_feedback_reviewer(self.request(self.local)))
        self.assertFalse(is_feedback_reviewer(self.request(AnonymousUser())))
        self.client.force_login(self.local)
        self.assertEqual(self.client.get(self.inbox, HTTP_HOST='a.example').status_code,
                         403)

    @override_settings(GT_FEEDBACK_REVIEWER=site_reviewers)
    def test_the_hook_decides_per_site(self):
        self.client.force_login(self.local)
        page = self.client.get(self.inbox, HTTP_HOST='a.example')
        self.assertContains(page, 'A one')
        self.assertNotContains(page, 'B one')
        self.assertEqual(self.client.get(self.inbox, HTTP_HOST='b.example').status_code,
                         403)
        # It answers too.
        response = self.client.post(self.detail, {'answer-status': 'reviewing',
                                                  'answer-response': 'Done.'},
                                    HTTP_HOST='a.example')
        self.assertEqual(response.status_code, 302)
        self.feedback.refresh_from_db()
        self.assertEqual((self.feedback.status, self.feedback.responded_by),
                         ('answered', self.local))
        # The global permissions no longer count.
        self.client.force_login(self.global_reviewer)
        self.assertEqual(self.client.get(self.inbox, HTTP_HOST='a.example').status_code,
                         403)

    @override_settings(
        GT_FEEDBACK_REVIEWER='djgentelella.tests.ProposalsW35_Test.site_reviewers',
        GT_FEEDBACK_ANSWERER=nobody_answers)
    def test_a_dotted_path_and_a_hook_to_answer(self):
        self.assertTrue(is_feedback_reviewer(self.request(self.local)))
        self.assertFalse(can_answer_feedback(self.request(self.local)))
        self.client.force_login(self.local)
        self.assertContains(self.client.get(self.detail, HTTP_HOST='a.example'),
                            'A one')
        self.assertEqual(self.client.post(self.detail, {'answer-status': 'closed'},
                                          HTTP_HOST='a.example').status_code, 404)


# -- D20 2: public views ---------------------------------------------------------------

class PublicViewTests(TestCase):
    def test_the_views_read_before_signing_in(self):
        theme = SiteTheme.objects.create(primary='#112233')
        public = [reverse('gt_theme_css', args=[theme.pk]),
                  reverse('gt_theme_logo', args=[theme.pk]),
                  reverse('gt_pwa_manifest'), reverse('gt_pwa_service_worker'),
                  reverse('gt_pwa_offline'), reverse('gt_push_resubscribe'),
                  reverse('login'), reverse('logout'), reverse('password_reset'),
                  reverse('password_reset_done'), reverse('password_reset_complete'),
                  reverse('password_reset_confirm', args=['x', 'y']),
                  reverse('djgentelella-js-catalog'), reverse('flag_sprite'),
                  reverse('flag_icon', args=['cr'])]
        for url in public:
            with self.subTest(url=url):
                self.assertTrue(is_public_view(resolve(url)))
        private = [reverse('gt_feedback_inbox'), reverse('gt_theme_roller'),
                   reverse('gt_push_preferences'), reverse('gt_push_subscribe'),
                   reverse('password_change')]
        for url in private:
            with self.subTest(url=url):
                self.assertFalse(is_public_view(resolve(url)))
        self.assertFalse(is_public_view(None))

    def test_marking_a_view_of_the_project(self):
        def view(request):
            return None

        self.assertFalse(is_public_view(view))
        self.assertIs(public_view(view), view)
        self.assertTrue(is_public_view(view))

        class Open(View):
            gt_public = True

        self.assertTrue(is_public_view(Open.as_view()))
        # Only True counts.
        view.gt_public = 'yes'
        self.assertFalse(is_public_view(view))


# -- D20 3: the PWA under the script prefix --------------------------------------------

class PwaPrefixTests(TestCase):
    def tearDown(self):
        set_script_prefix('/')
        super().tearDown()

    def manifest(self):
        return build_manifest(RequestFactory().get('/'))

    def test_the_script_prefix_by_default(self):
        self.assertEqual(self.manifest()['scope'], '/')
        set_script_prefix('/a/ventas/')
        manifest = self.manifest()
        self.assertEqual((manifest['scope'], manifest['start_url']),
                         ('/a/ventas/', '/a/ventas/'))
        self.assertEqual(worker_config(RequestFactory().get('/'))['scope'],
                         '/a/ventas/')

    @override_settings(GT_PWA_SCOPE='/app/')
    def test_the_setting_wins(self):
        set_script_prefix('/a/ventas/')
        self.assertEqual(self.manifest()['scope'], '/app/')

    def test_served_under_a_prefix(self):
        # What a WSGI server (SCRIPT_NAME) or a middleware of the consumer
        # does before the view runs.
        set_script_prefix('/a/ventas/')
        response = self.client.get('/pwa/sw.js')
        self.assertEqual(response['Service-Worker-Allowed'], '/a/ventas/')
        response = self.client.get('/pwa/manifest.webmanifest')
        self.assertEqual(json.loads(response.content)['start_url'], '/a/ventas/')


# -- D20 4: the login page with blocks -------------------------------------------------

@override_settings(LANGUAGE_CODE='en')
class LoginBlocksTests(TestCase):
    def render(self, source):
        request = RequestFactory().get('/accounts/login/')
        request.user = AnonymousUser()
        return engines['django'].from_string(source).render({}, request)

    def test_the_page_is_as_before(self):
        page = self.client.get(reverse('login'), {'next': '/x/'})
        self.assertContains(page, 'name="username"')
        self.assertContains(page, 'Please login to see this page.')

    def test_a_project_fills_the_blocks(self):
        html = self.render(
            "{% extends 'gentelella/registration/login.html' %}"
            "{% block login_providers %}<a id='w35-oidc' href='/oidc/'>SSO</a>"
            "{% endblock %}"
            "{% block login_messages %}<p id='w35-note'>Hello</p>{% endblock %}")
        self.assertIn("id='w35-oidc'", html)
        self.assertIn("id='w35-note'", html)
        self.assertIn('name="password"', html)
        html = self.render(
            "{% extends 'gentelella/registration/login.html' %}"
            "{% block login_form %}<p id='w35-form'>Own form</p>{% endblock %}")
        self.assertIn("id='w35-form'", html)
        self.assertNotIn('name="password"', html)


# -- D20 5: the user menu --------------------------------------------------------------

@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS,
                   ALLOWED_HOSTS=['*'])
class UserMenuTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user('ana')
        self.item = MenuItem.objects.create(
            key='gt-user-menu', title='User', category='main', is_widget=True,
            url_name='gt-user-menu', icon='fa fa-user')

    def tearDown(self):
        unregister_user_menu_entry('w35-profile')
        super().tearDown()

    def request(self, user):
        request = RequestFactory().get('/')
        request.user = user
        return request

    def render(self, user):
        return UserMenu({'id': 'tm_1', 'item': self.item,
                         'context': {'request': self.request(user)}}).render()

    def test_registered_as_a_menu_widget(self):
        self.assertIs(get_menu_widget('gt-user-menu'), UserMenu)
        self.assertIs(get_menu_widget('djgentelella.menu_widgets.user.UserMenu'),
                      UserMenu)

    @override_settings(GT_PWA_MANIFEST=False, GT_PWA_SERVICE_WORKER=False)
    def test_the_entries_of_djgentelella(self):
        html = self.render(self.user)
        self.assertIn('ana', html)
        self.assertRegex(html, r'<form method="post" action="/accounts/logout/"')
        self.assertIn('id="gt-user-logout"', html)
        # Push only when the PWA is on, the inbox only for reviewers.
        self.assertNotIn('id="gt-user-push"', html)
        self.assertNotIn('id="gt-user-feedback"', html)
        with override_settings(GT_PWA_MANIFEST=True, GT_FEEDBACK=True):
            html = self.render(make_user('rev', 'djgentelella.view_feedback'))
        self.assertIn('id="gt-user-push" href="/pwa/push/"', html)
        self.assertIn('id="gt-user-feedback" href="/gt-feedback/"', html)
        self.assertEqual(self.render(AnonymousUser()), '')

    def test_a_project_adds_an_entry(self):
        register_user_menu_entry('w35-profile', '<Profile>', '/profile/',
                                 icon='fa fa-id-card', position=50,
                                 visible=lambda request: request.user.username == 'ana')
        keys = [entry['key'] for entry in user_menu_entries(self.request(self.user))]
        self.assertEqual(keys[0], 'w35-profile')
        self.assertEqual(keys[-1], 'logout')
        html = self.render(self.user)
        self.assertIn('id="gt-user-w35-profile" href="/profile/"', html)
        self.assertIn('&lt;Profile&gt;', html)
        self.assertNotIn('w35-profile', self.render(make_user('beto')))
        # A URL name that does not reverse leaves the entry out.
        register_user_menu_entry('w35-profile', 'Profile', 'no-such-url-name')
        self.assertNotIn('w35-profile', self.render(self.user))
        unregister_user_menu_entry('w35-profile')
        self.assertNotIn('w35-profile', registered_user_menu_entries())

    def test_bad_entries(self):
        with self.assertRaises(ValueError):
            register_user_menu_entry('', 'X', '/x/')
        with self.assertRaises(ValueError):
            register_user_menu_entry('w35-profile', 'X', '/x/', method='delete')

    def test_drawn_in_the_top_bar(self):
        self.client.force_login(self.user)
        page = self.client.get(reverse('home'))
        self.assertContains(page, 'id="gt-user-logout"')


# -- D20 6: #rgb in a theme ------------------------------------------------------------

@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS)
class ShortColourTests(TestCase):
    def test_normalize(self):
        self.assertEqual(values.normalize_color(' #ABC '), '#aabbcc')
        self.assertEqual(values.normalize_color('#A0B1C2'), '#a0b1c2')
        self.assertEqual(values.normalize_color('#abcd'), '#abcd')
        self.assertEqual(values.normalize_color('red'), 'red')
        self.assertIsNone(values.normalize_color(None))

    def test_the_model_and_the_form(self):
        theme = SiteTheme(primary='#F00', secondary='#123456')
        theme.full_clean()
        self.assertEqual((theme.primary, theme.secondary), ('#ff0000', '#123456'))
        theme.save()
        theme.refresh_from_db()
        self.assertEqual(theme.primary, '#ff0000')
        SiteTheme.objects.filter(pk=theme.pk).update(danger='#FFF')
        theme.refresh_from_db()
        theme.save()
        self.assertEqual(SiteTheme.objects.get(pk=theme.pk).danger, '#ffffff')
        with self.assertRaises(ValidationError):
            SiteTheme(primary='#abcd').full_clean()
        form = SiteThemeForm({'primary': '#0a0', 'font': ''},
                             instance=SiteTheme(site=Site.objects.create(
                                 domain='w35.example', name='W35')))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().primary, '#00aa00')
        self.assertIn('pattern="#(?:[0-9a-fA-F]{3}){1,2}"', str(form['primary']))

    def test_the_preview(self):
        self.client.force_login(make_user('roller', 'djgentelella.change_sitetheme'))
        css = self.client.get(reverse('gt_theme_preview'), {'primary': '#f00'})
        self.assertIn('--bs-primary:#ff0000', css.content.decode().replace(' ', ''))


# -- D21 1: widgets of the project -----------------------------------------------------

class PromptTextarea(Textarea):
    """A widget of a project with an option."""

    def __init__(self, prompt='', attrs=None):
        self.prompt = prompt
        super().__init__(attrs=attrs, actions=[
            WidgetAction('Generate', icon='fa fa-magic',
                         attrs={'data-prompt': prompt})] if prompt else None)


PROMPT_PATH = 'djgentelella.tests.ProposalsW35_Test.PromptTextarea'
PROMPT_OPTIONS = {'prompt': {'type': 'string', 'maxLength': 20, 'title': 'Prompt'}}


class RegisterWidgetTests(SimpleTestCase):
    def tearDown(self):
        widgetmap.unregister_widget('PromptTextarea')
        super().tearDown()

    def test_offered_and_built(self):
        defaults = {kind: widgetmap.widget_choices(kind)[0]
                    for kind in widgetmap.WIDGETS_BY_KIND}
        widgetmap.register_widget('PromptTextarea', PROMPT_PATH, PROMPT_OPTIONS,
                                  kinds=('text', 'string'))
        self.assertEqual(widgetmap.widget_choices('text')[-1], 'PromptTextarea')
        self.assertIn('PromptTextarea', widgetmap.widget_choices('string'))
        self.assertNotIn('PromptTextarea', widgetmap.widget_choices('integer'))
        # No default changes.
        self.assertEqual({kind: widgetmap.widget_choices(kind)[0]
                          for kind in widgetmap.WIDGETS_BY_KIND}, defaults)
        widget = widgetmap.build_widget('PromptTextarea', {'prompt': 'summary'})
        self.assertIsInstance(widget, PromptTextarea)
        self.assertEqual(widget.prompt, 'summary')
        self.assertEqual(widgetmap.widget_options('PromptTextarea')['properties'],
                         PROMPT_OPTIONS)
        self.assertTrue(widgetmap.validate_widget_options(
            'PromptTextarea', {'prompt': 'x' * 21}))
        self.assertTrue(widgetmap.validate_widget_options(
            'PromptTextarea', {'other': 1}))

    def test_checks_and_replacing(self):
        def no_x(options, path):
            return ['no x'] if options.get('prompt') == 'x' else []

        widgetmap.register_widget('PromptTextarea', PROMPT_PATH, PROMPT_OPTIONS,
                                  kinds=('text',), checks=no_x)
        self.assertEqual(widgetmap.validate_widget_options(
            'PromptTextarea', {'prompt': 'x'}), ['no x'])
        widgetmap.register_widget('PromptTextarea', PROMPT_PATH, kinds=('string',))
        self.assertNotIn('PromptTextarea', widgetmap.widget_choices('text'))
        self.assertEqual(widgetmap.validate_widget_options('PromptTextarea', {}), [])
        self.assertTrue(widgetmap.validate_widget_options(
            'PromptTextarea', {'prompt': 'x'}))
        widgetmap.unregister_widget('PromptTextarea')
        self.assertNotIn('PromptTextarea', widgetmap.WIDGETS)
        self.assertNotIn('PromptTextarea', widgetmap.widget_choices('string'))

    def test_refused(self):
        for args in [('Textarea', PROMPT_PATH), ('bad key', PROMPT_PATH),
                     ('PromptTextarea', 'nodots'),
                     ('PromptTextarea', PROMPT_PATH, ['not a dict'])]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                widgetmap.register_widget(*args)
        with self.assertRaises(ValueError):
            widgetmap.register_widget('PromptTextarea', PROMPT_PATH, kinds=('nokind',))
        # djgentelella's own stay.
        widgetmap.unregister_widget('Textarea')
        self.assertIn('Textarea', widgetmap.WIDGETS)


class RegisteredWidgetInADesignTests(DataDesignTestCase):
    def tearDown(self):
        widgetmap.unregister_widget('PromptTextarea')
        super().tearDown()

    def document(self):
        return design(
            node('object_management', 'products', {
                'model': 'demoapp.Product', 'form': 'product_form',
                'list_fields': ['name']}),
            forms={'product_form': {
                'model': 'demoapp.Product',
                'fields': ['name', 'description', 'price'],
                'widgets': {'description': 'PromptTextarea'},
                'widget_options': {'description': {'prompt': 'summary'}}}},
            url='w35-products/', url_name='w35-products')

    def test_a_design_form_uses_it(self):
        self.assertTrue(self.errors(self.document()))
        widgetmap.register_widget('PromptTextarea', PROMPT_PATH, PROMPT_OPTIONS,
                                  kinds=('text',))
        self.assertEqual(self.errors(self.document()), [])
        page = self.publish(self.document(), path='w35-products')
        build = engine.resolve_page(page)[0].nodes['products'].build
        form = build.form.get_form(prefix='x')
        self.assertIsInstance(form.fields['description'].widget, PromptTextarea)
        self.assertEqual(form.fields['description'].widget.prompt, 'summary')


# -- D21 2: tags on the steps ----------------------------------------------------------

class ProcessTagsTests(SimpleTestCase):
    def tearDown(self):
        pipeline.unregister_process('w35.summary')
        pipeline.unregister_process('w35.plain')
        super().tearDown()

    def test_tags(self):
        pipeline.register_process('w35.summary', lambda ctx: None, kind='process',
                                  tags=('ai', 'text', 'ai'))
        pipeline.register_process('w35.plain', lambda ctx: None, kind='process')
        self.assertEqual(pipeline.get_process('w35.summary').tags, ('ai', 'text'))
        self.assertEqual(pipeline.get_process('w35.plain').tags, ())
        self.assertEqual(list(pipeline.registered_processes(tag='ai')), ['w35.summary'])
        self.assertEqual(list(pipeline.registered_processes('validation', tag='ai')),
                         [])
        entries = {entry['name']: entry for entry in pipeline.catalogue()}
        self.assertEqual(entries['w35.summary']['tags'], ['ai', 'text'])
        self.assertEqual(entries['w35.plain']['tags'], [])
        self.assertEqual([entry['name'] for entry in pipeline.catalogue(tag='ai')],
                         ['w35.summary'])
        # One text is one tag.
        pipeline.register_process('w35.plain', lambda ctx: None, kind='process',
                                  tags='ai')
        self.assertEqual(pipeline.get_process('w35.plain').tags, ('ai',))

    def test_the_decorator_and_bad_tags(self):
        @pipeline.process('w35.summary', kind='computation', tags=['ai'])
        def summary(ctx):
            return None

        self.assertEqual(pipeline.get_process('w35.summary').tags, ('ai',))
        for tags in [(1,), ('',), 5]:
            with self.subTest(tags=tags), self.assertRaises(ImproperlyConfigured):
                pipeline.register_process('w35.plain', lambda ctx: None,
                                          kind='process', tags=tags)


# -- D21 3: the key of a row -----------------------------------------------------------

def remote_rows(request):
    return Product.objects.none()


class RowKeyTests(SimpleTestCase):
    columns = [Column('code', 'Code', 'string'), Column('name', 'Name', 'string')]

    def test_a_source_over_a_model(self):
        source = ModelDataSource(Product, name='w35.products', fields=['name'])
        self.assertEqual(source.row_key({'pk': 7, 'name': 'Apple'}), '7')
        self.assertEqual(restricted(source, ['name']).row_key({'pk': 7}), '7')

    def test_key_columns(self):
        source = FunctionDataSource(remote_rows, self.columns, name='w35.remote',
                                    key_columns=['code'])
        self.assertEqual(source.row_key({'pk': 1, 'code': 'CR-1', 'name': 'x'}),
                         'CR-1')
        source.key_columns = ('code', 'name')
        self.assertEqual(source.row_key({'pk': 1, 'code': 'CR-1', 'name': 'é'}),
                         '["CR-1","é"]')
        self.assertEqual(restricted(source, ['code']).row_key(
            {'code': 'CR-1', 'name': 'é'}), '["CR-1","é"]')

    def test_a_hash_without_key(self):
        source = FunctionDataSource(remote_rows, self.columns, name='w35.remote')
        key = source.row_key({'pk': 1, 'code': 'CR-1', 'name': 'x'})
        self.assertRegex(key, r'^h:[0-9a-f]{40}$')
        # Neither the position (pk) nor the order of the keys count.
        self.assertEqual(source.row_key({'name': 'x', 'code': 'CR-1', 'pk': 9}), key)
        self.assertNotEqual(source.row_key({'code': 'CR-1', 'name': 'y'}), key)

    def test_a_long_key_is_hashed(self):
        source = FunctionDataSource(remote_rows, self.columns, name='w35.remote',
                                    key_columns=['code'])
        key = source.row_key({'code': 'x' * 300})
        self.assertLessEqual(len(key), ROW_KEY_MAX_LENGTH)
        self.assertTrue(key.startswith('h:'))
        self.assertEqual(key, source.row_key({'code': 'x' * 300}))


# -- D21 4: a text area with buttons ---------------------------------------------------

class TextareaActionsTests(SimpleTestCase):
    def test_without_actions_nothing_changes(self):
        html = forms.CharField(widget=Textarea).widget.render('body', 'Hi',
                                                              {'id': 'id_body'})
        self.assertTrue(html.lstrip().startswith('<textarea'), html)
        self.assertNotIn('gt-widget-actions', html)

    def test_the_buttons_under_the_field(self):
        widget = Textarea(actions=[
            WidgetAction('<Generate>', icon='fa fa-magic',
                         attrs={'data-url': '/ai/"x"/', 'title': 'AI'}),
            {'label': 'Clear', 'css_class': 'btn btn-link'}])
        html = widget.render('body', '', {'id': 'id_body'})
        self.assertIn('<div class="gt-textarea-with-actions">', html)
        buttons = re.findall(r'<button [^>]*>', html)
        self.assertEqual(len(buttons), 2)
        self.assertIn('data-gt-target="id_body"', buttons[0])
        self.assertIn('data-url="/ai/&quot;x&quot;/"', buttons[0])
        self.assertIn('&lt;Generate&gt;', html)
        self.assertIn('class="btn btn-link"', buttons[1])

    def test_a_subclass_and_refused_attributes(self):
        html = PromptTextarea('summary').render('body', '', {'id': 'id_body'})
        self.assertIn('data-prompt="summary"', html)
        for name in ('onclick', 'style', 'href', 'data-x" onclick="y'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                WidgetAction('X', attrs={name: '1'})
        with self.assertRaises(ValueError):
            Textarea(actions=['not an action'])


# -- E15 3: master-detail in the engine ------------------------------------------------

class MasterDetailTests(DataDesignTestCase):
    def document(self, master_detail=True):
        document = design(
            node('object_management', 'categories', {
                'model': 'demoapp.ProductCategory', 'form': 'category_form',
                'list_fields': ['name']}),
            forms={'category_form': {'model': 'demoapp.ProductCategory',
                                     'fields': ['name']}},
            url='w35-master/', url_name='w35-master',
            parent={'model': 'demoapp.ProductCategory'})
        if master_detail:
            document['root']['children'][0]['meta'] = {'master_detail': {
                'variant': 'side_by_side', 'master': 'categories'}}
        return document

    def config(self, response):
        found = re.search(r'<script id="categories_gtconfig" type="application/json">'
                          r'(.*?)</script>', response.content.decode(), re.S)
        self.assertIsNotNone(found, response.content.decode()[:500])
        return json.loads(found.group(1))

    def test_master_detail_of(self):
        document = self.document()
        self.assertEqual(master_detail_of(document, 'categories')['variant'],
                         'side_by_side')
        self.assertIsNone(master_detail_of(document, 'other'))
        self.assertIsNone(master_detail_of(self.document(False), 'categories'))
        self.assertIsNone(master_detail_of({}, 'categories'))

    def test_the_master_is_marked_and_chosen(self):
        self.grant('demoapp.view_productcategory')
        self.publish(self.document(), path='w35-master')
        response = self.client.get(reverse('gt-design-page', args=[
            'w35-master/%d' % self.food.pk]))
        self.assertEqual(response.status_code, 200)
        master = self.config(response)['master']
        self.assertEqual(master['current'], str(self.food.pk))
        self.assertEqual(master['variant'], 'side_by_side')
        self.assertEqual(master['url'].replace(master['placeholder'], '5'),
                         reverse('gt-design-page', args=['w35-master/5']))

    def test_without_master_detail(self):
        self.grant('demoapp.view_productcategory')
        self.publish(self.document(False), path='w35-master')
        response = self.client.get(reverse('gt-design-page', args=[
            'w35-master/%d' % self.food.pk]))
        self.assertNotIn('master', self.config(response))
        self.assertTrue(Page.objects.filter(path='w35-master').exists())
