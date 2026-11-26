"""W32: the theme roller per Site, the diagram of a flow instance, user
feedback and the choices of a relation limited by Site.

Classes prefixed ``W32`` so the ``import *`` of ``tests/__init__.py`` never
shadows another module's.
"""

import json
import shutil
import tempfile
from io import BytesIO

from django.contrib.auth.models import AnonymousUser, Permission, User
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIRequestFactory

from demoapp.models import Country, Department, NewHire
from djgentelella.designs.exposure import expose, site_choices, site_field_of
from djgentelella.flows import Flow, Transition, register_flow
from djgentelella.models import Feedback, Notification, SiteTheme
from djgentelella.tests.Designs_Test import design, node
from djgentelella.tests.DesignsData_Test import DataDesignTestCase
from djgentelella.theme.css import render_css
from djgentelella.theme.forms import SiteThemeForm
from djgentelella.utils import set_settings
from djgentelella.views.select2autocomplete import BaseSelect2View

FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']


def make_user(name, *codenames, superuser=False):
    if superuser:
        return User.objects.create_superuser(name, password='x')
    user = User.objects.create_user(name, password='x')
    for codename in codenames:
        app_label, code = codename.split('.')
        user.user_permissions.add(Permission.objects.get(
            content_type__app_label=app_label, codename=code))
    return User.objects.get(pk=user.pk)


def image_file(name, image_format='PNG', size=(8, 8)):
    stream = BytesIO()
    Image.new('RGB', size, (200, 30, 30)).save(stream, image_format)
    return SimpleUploadedFile(name, stream.getvalue())


# -- theme roller -------------------------------------------------------------------

@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS,
                   ALLOWED_HOSTS=['*'])
class W32ThemeTests(TestCase):
    def setUp(self):
        cache.clear()
        Site.objects.clear_cache()
        self.site_a = Site.objects.create(domain='a.example', name='A')
        self.site_b = Site.objects.create(domain='b.example', name='B')
        self.site_c = Site.objects.create(domain='c.example', name='C')
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, True)

    def link(self, host):
        request = RequestFactory().get('/', HTTP_HOST=host)
        return Template('{% load gttheme %}{% gt_theme_css %}').render(
            Context({'request': request}))

    def css(self, link, host='a.example'):
        url = link.split('href="')[1].split('"')[0].replace('&amp;', '&')
        return self.client.get(url, HTTP_HOST=host)

    def test_one_theme_per_site(self):
        SiteTheme.objects.create(site=self.site_a, primary='#112233', border_radius=2)
        SiteTheme.objects.create(site=self.site_b, primary='#445566', font='serif')
        SiteTheme.objects.create(site=None, primary='#778899')
        css_a = self.css(self.link('a.example')).content.decode()
        css_b = self.css(self.link('b.example')).content.decode()
        self.assertIn('--bs-primary:#112233', css_a)
        self.assertIn('--bs-primary-rgb:17,34,51', css_a)
        self.assertIn('--bs-border-radius:2px', css_a)
        self.assertIn('.btn-primary{--bs-btn-color:#ffffff;--bs-btn-bg:#112233', css_a)
        self.assertNotIn('#445566', css_a)
        self.assertIn('--bs-primary:#445566', css_b)
        self.assertIn('Georgia', css_b)
        # A Site without its own theme uses the global one; a host without
        # a Site too.
        self.assertIn('--bs-primary:#778899',
                      self.css(self.link('c.example')).content.decode())
        self.assertIn('--bs-primary:#778899',
                      self.css(self.link('nowhere.example')).content.decode())

    def test_no_theme_no_link(self):
        self.assertEqual(self.link('a.example'), '')

    def test_invalid_values_are_refused(self):
        theme = SiteTheme(site=self.site_a, primary='red;}body{display:none',
                          border_radius=99)
        with self.assertRaises(ValidationError) as caught:
            theme.full_clean()
        self.assertIn('primary', caught.exception.message_dict)
        self.assertIn('border_radius', caught.exception.message_dict)
        form = SiteThemeForm({'primary': '#12345', 'sidebar_bg': 'url(x)',
                              'font': '"Comic"', 'border_radius': '-1'},
                             instance=SiteTheme(site=self.site_a))
        self.assertFalse(form.is_valid())
        self.assertEqual(set(form.errors),
                         {'primary', 'sidebar_bg', 'font', 'border_radius'})
        # Whatever reaches the writer anyway is left out, never copied.
        css = render_css({'primary': 'red;}*{x:y', 'danger': '#ABCDEF',
                          'font': 'x;}', 'border_radius': 400,
                          'sidebar_text': '#fff'})
        self.assertNotIn('red', css)
        self.assertNotIn('x:y', css)
        self.assertNotIn('#fff;', css)
        self.assertNotIn('font-family', css)
        self.assertNotIn('border-radius', css)
        self.assertIn('--bs-danger:#abcdef', css)

    def test_version_changes_when_saved(self):
        theme = SiteTheme.objects.create(site=self.site_a, primary='#112233')
        first = self.link('a.example')
        self.assertIn('?v=1"', first)
        response = self.css(first)
        self.assertEqual(response['Content-Type'], 'text/css; charset=utf-8')
        self.assertEqual(response['Cache-Control'], 'public, max-age=31536000, '
                                                    'immutable')
        theme.primary = '#aa0000'
        theme.save()
        second = self.link('a.example')
        self.assertIn('?v=2"', second)
        self.assertIn('--bs-primary:#aa0000', self.css(second).content.decode())
        # The old URL answers the current theme, but not to keep it.
        stale = self.css(first)
        self.assertEqual(stale['Cache-Control'], 'no-cache')
        self.assertIn('--bs-primary:#aa0000', stale.content.decode())
        # Unchanged since the browser's copy: 304.
        response = self.client.get(reverse('gt_theme_css', args=[theme.pk]),
                                   {'v': 2}, HTTP_IF_NONE_MATCH='"gttheme-2"')
        self.assertEqual(response.status_code, 304)

    def test_one_global_theme(self):
        SiteTheme.objects.create(site=None, primary='#111111')
        with self.assertRaises(ValidationError):
            SiteTheme(site=None, primary='#222222').full_clean()

    def test_roller_page(self):
        url = reverse('gt_theme_roller')
        nobody = make_user('nobody')
        self.client.force_login(nobody)
        self.assertEqual(self.client.get(url, HTTP_HOST='a.example').status_code, 403)
        admin = make_user('admin', 'djgentelella.change_sitetheme',
                          'djgentelella.add_sitetheme')
        self.client.force_login(admin)
        page = self.client.get(url, HTTP_HOST='a.example')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'id="gt-theme-preview-css"')
        response = self.client.post(url, {'site': self.site_a.pk, 'primary': '#123abc',
                                          'border_radius': '6', 'font': 'mono'},
                                    HTTP_HOST='a.example')
        self.assertEqual(response.status_code, 302)
        theme = SiteTheme.objects.get(site=self.site_a)
        self.assertEqual((theme.primary, theme.border_radius, theme.font),
                         ('#123abc', 6, 'mono'))
        response = self.client.post(url, {'site': self.site_a.pk,
                                          'primary': 'javascript:alert(1)'},
                                    HTTP_HOST='a.example')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SiteTheme.objects.get(site=self.site_a).primary, '#123abc')
        # The global theme from the same page.
        self.client.post(url, {'site': 'global', 'primary': '#000080'},
                         HTTP_HOST='a.example')
        self.assertEqual(SiteTheme.objects.get(site=None).primary, '#000080')
        # Removing a theme.
        self.client.post(url, {'site': self.site_a.pk, 'reset': '1'},
                         HTTP_HOST='a.example')
        self.assertFalse(SiteTheme.objects.filter(site=self.site_a).exists())
        self.assertEqual(self.client.get(url, {'site': '9999'}).status_code, 404)

    def test_preview_only_writes_valid_values(self):
        admin = make_user('admin', 'djgentelella.change_sitetheme')
        self.client.force_login(admin)
        response = self.client.get(reverse('gt_theme_preview'), {
            'primary': '#00ff00', 'secondary': '}body{', 'border_radius': '4'})
        css = response.content.decode()
        self.assertIn('--bs-primary:#00ff00', css)
        self.assertNotIn('body{', css.replace('body.nav-md', ''))
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.client.logout()
        self.assertEqual(self.client.get(reverse('gt_theme_preview')).status_code, 302)

    def test_preview_with_a_radius_that_is_not_a_number(self):
        # The reproduction: '²' passed str.isdigit() and int() raised (500).
        self.client.force_login(make_user('admin', 'djgentelella.change_sitetheme'))
        for radius in ('²', '٣', '-1', 'x'):
            response = self.client.get(reverse('gt_theme_preview'),
                                       {'border_radius': radius})
            self.assertEqual(response.status_code, 200, radius)
        response = self.client.get(reverse('gt_theme_preview'),
                                   {'border_radius': '12'})
        self.assertIn('12px', response.content.decode())

    def test_logo(self):
        with self.settings(MEDIA_ROOT=self.media):
            form = SiteThemeForm({}, {'logo': image_file('logo.png')},
                                 instance=SiteTheme(site=self.site_a))
            self.assertTrue(form.is_valid(), form.errors)
            theme = form.save()
            response = self.client.get(reverse('gt_theme_logo', args=[theme.pk]),
                                       {'v': theme.version})
            self.assertEqual(response['Content-Type'], 'image/png')
            self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
            request = RequestFactory().get('/', HTTP_HOST='a.example')
            logo = Template('{% load gttheme %}{% gt_theme_logo_url %}').render(
                Context({'request': request}))
            self.assertIn(reverse('gt_theme_logo', args=[theme.pk]), logo)
            # An SVG, something that is not an image, a PNG named .jpg.
            for upload in (SimpleUploadedFile('logo.svg', b'<svg onload="x()"/>'),
                           SimpleUploadedFile('logo.png', b'not an image'),
                           image_file('logo.jpg')):
                form = SiteThemeForm({}, {'logo': upload},
                                     instance=SiteTheme(site=self.site_b))
                self.assertFalse(form.is_valid())
                self.assertIn('logo', form.errors)
            with self.settings(GT_THEME_LOGO_MAX_BYTES=10):
                form = SiteThemeForm({}, {'logo': image_file('big.png')},
                                     instance=SiteTheme(site=self.site_b))
                self.assertFalse(form.is_valid())
            # Removing it.
            form = SiteThemeForm({'clear_logo': 'on'}, instance=theme)
            self.assertTrue(form.is_valid(), form.errors)
            self.assertFalse(form.save().logo)


# -- the diagram of an instance -----------------------------------------------------

@register_flow
class W32DiagramFlow(Flow):
    name = 'tests.w32_diagram'
    title = 'Approval'
    model = Country
    states = [('draft', 'Draft'), ('review', 'Review'), ('done', 'Done'),
              ('gone', 'Gone')]
    initial = 'draft'
    transitions = [
        Transition('submit', 'draft', 'review', label='Submit',
                   perms=['demoapp.change_country']),
        Transition('approve', 'review', 'done', label='Approve',
                   perms=['demoapp.delete_country']),
        Transition('back', 'review', 'draft', label='Back',
                   perms=['demoapp.change_country']),
        Transition('drop', 'draft', 'gone', label='Drop',
                   perms=['demoapp.change_country']),
    ]


@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS)
class W32DiagramTests(TestCase):
    def setUp(self):
        self.flow = W32DiagramFlow()
        self.country = Country.objects.create(name='Chile')
        self.boss = make_user('boss', 'demoapp.change_country',
                              'demoapp.delete_country', 'demoapp.view_country')
        self.clerk = make_user('clerk', 'demoapp.change_country',
                               'demoapp.view_country')
        self.flow.start(self.country, self.boss)
        self.flow.run(self.country, 'submit', self.boss)

    def edges(self, svg, flag):
        """``(source, target)`` of the edges with the class ``flag``, read from
        the label groups (which carry no path)."""
        found = []
        for part in svg.split('<g class="gt-flow-edge')[1:]:
            classes = part.split('"')[0].split()
            if flag in classes and '<path' in part.split('</g>')[0]:
                found.append(part.split('d="')[1].split('"')[0])
        return found

    def test_current_way_and_available(self):
        svg = str(self.flow.instance_diagram(self.country, self.boss))
        self.assertIn('data-state="review" data-type="state" data-status="active"', svg)
        self.assertIn('data-state="draft" data-type="state" '
                      'data-status="completed"', svg)
        self.assertEqual(len(self.edges(svg, 'taken')), 1)
        # From review the boss may approve or go back; drop leaves draft.
        self.assertIn('data-transition="approve"', svg)
        self.assertIn('data-transition="back"', svg)
        self.assertNotIn('data-transition="drop"', svg)
        self.assertNotIn('data-transition="submit"', svg)
        # Said in words for a screen reader.
        self.assertIn('role="img" aria-labelledby="', svg)
        self.assertIn('Approval: current state Review</title>', svg)
        self.assertIn('Way taken: Draft → Review.', svg)
        self.assertIn('You can run: Approve, Back.', svg)

    def test_available_follows_the_permissions(self):
        svg = str(self.flow.instance_diagram(self.country, self.clerk))
        self.assertIn('data-transition="back"', svg)
        self.assertNotIn('data-transition="approve"', svg)
        self.assertIn('You can run: Back.', svg)
        nobody = make_user('nobody')
        svg = str(self.flow.instance_diagram(self.country, nobody))
        self.assertEqual(self.edges(svg, 'available'), [])
        self.assertIn('You cannot run any transition now.', svg)

    def test_a_way_back_is_taken_too(self):
        self.flow.run(self.country, 'back', self.boss)
        runtime = self.flow.runtime(self.flow.get_instance(self.country,
                                                           create=False))
        self.assertEqual(runtime['path'], ['draft', 'review', 'draft'])
        self.assertEqual([item[2] for item in runtime['taken']], ['submit', 'back'])
        svg = str(self.flow.instance_diagram(self.country, self.boss))
        self.assertEqual(len(self.edges(svg, 'taken')), 2)
        self.assertIn('data-transition="drop"', svg)

    def test_template_tag_finds_the_flow(self):
        request = RequestFactory().get('/')
        request.user = self.clerk
        rendered = Template('{% load gtflows %}{% flow_diagram country %}').render(
            Context({'request': request, 'country': self.country}))
        self.assertIn('Approval: current state Review', rendered)
        self.assertIn('data-transition="back"', rendered)
        named = Template("{% load gtflows %}{% flow_diagram country "
                         "flow='tests.w32_diagram' %}").render(
            Context({'request': request, 'country': self.country}))
        self.assertIn('Approval: current state Review', named)
        bare = Template("{% load gtflows %}{% flow_diagram 'tests.w32_diagram' %}"
                        ).render(Context({'request': request}))
        self.assertNotIn('data-status', bare)
        # An object without an instance, of a model with several flows.
        other = Country.objects.create(name='Peru')
        empty = Template('{% load gtflows %}{% flow_diagram country %}').render(
            Context({'request': request, 'country': other}))
        self.assertEqual(empty.strip(), '')

    def test_detail_page(self):
        self.client.force_login(self.clerk)
        page = self.client.get(reverse('flow_detail',
                                       args=[self.flow.name, self.country.pk]))
        self.assertContains(page, 'data-transition="back"')
        self.assertContains(page, 'current state Review')


# -- feedback -----------------------------------------------------------------------

@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS,
                   ALLOWED_HOSTS=['*'], GT_FEEDBACK=True)
class W32FeedbackTests(TestCase):
    def setUp(self):
        cache.clear()
        Site.objects.clear_cache()
        self.site_a = Site.objects.create(domain='a.example', name='A')
        self.site_b = Site.objects.create(domain='b.example', name='B')
        self.author = make_user('author')
        self.reviewer = make_user('reviewer', 'djgentelella.view_feedback',
                                  'djgentelella.change_feedback')
        self.reader = make_user('reader', 'djgentelella.view_feedback')

    def button(self, user, host='a.example'):
        request = RequestFactory().get('/somewhere/', HTTP_HOST=host)
        request.user = user
        return Template('{% load gtfeedback %}{% gt_feedback_button %}').render(
            Context({'request': request}))

    def send(self, host='a.example', **data):
        values = {'gtfeedback-kind': 'bug', 'gtfeedback-text': 'It breaks',
                  'gtfeedback-url': '/orders/?secret=1#x',
                  'gtfeedback-page': 'orders', 'gtfeedback-browser': 'Firefox | 1x1'}
        values.update(data)
        return self.client.post(reverse('gt_feedback_create'), values, HTTP_HOST=host,
                                HTTP_ACCEPT='application/json')

    def test_created_with_the_page(self):
        self.assertIn('gt-feedback-modal', self.button(self.author))
        self.client.force_login(self.author)
        response = self.send()
        self.assertEqual(response.status_code, 200, response.content)
        feedback = Feedback.objects.get(pk=response.json()['id'])
        self.assertEqual((feedback.user, feedback.site, feedback.kind, feedback.status),
                         (self.author, self.site_a, 'bug', 'new'))
        # The path only: the query string can carry what a form typed.
        self.assertEqual(feedback.url, '/orders/')
        self.assertEqual(feedback.page, 'orders')
        self.assertEqual(feedback.browser, 'Firefox | 1x1')

    def test_what_is_cleaned(self):
        self.client.force_login(self.author)
        response = self.send(**{'gtfeedback-url': 'https://evil.example/x',
                                'gtfeedback-page': '<script>',
                                'gtfeedback-browser': 'a\nb'})
        feedback = Feedback.objects.get(pk=response.json()['id'])
        self.assertEqual((feedback.url, feedback.page, feedback.browser),
                         ('', '', 'a b'))
        self.assertEqual(self.send(**{'gtfeedback-url': '//evil.example/x'}
                                   ).status_code, 200)
        self.assertEqual(Feedback.objects.latest('pk').url, '')
        response = self.send(**{'gtfeedback-text': '   '})
        self.assertEqual(response.status_code, 400)
        self.assertIn('text', response.json()['errors'])
        response = self.send(**{'gtfeedback-kind': 'praise'})
        self.assertEqual(response.status_code, 400)

    def test_only_reviewers_see_it(self):
        mine = Feedback.objects.create(user=self.author, site=self.site_a, text='A one')
        theirs = Feedback.objects.create(user=self.author, site=self.site_b,
                                         text='B one')
        inbox = reverse('gt_feedback_inbox')
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(inbox, HTTP_HOST='a.example').status_code, 403)
        # Its author reads it; nobody else without the permission.
        detail = reverse('gt_feedback_detail', args=[mine.pk])
        response = self.client.get(detail, HTTP_HOST='a.example')
        self.assertEqual(response.status_code, 200)
        self.client.force_login(make_user('other'))
        response = self.client.get(detail, HTTP_HOST='a.example')
        self.assertEqual(response.status_code, 404)
        self.client.force_login(self.reviewer)
        page = self.client.get(inbox, HTTP_HOST='a.example')
        self.assertContains(page, 'A one')
        self.assertNotContains(page, 'B one')
        self.assertEqual(self.client.get(
            reverse('gt_feedback_detail', args=[theirs.pk]),
            HTTP_HOST='a.example').status_code, 404)
        page = self.client.get(inbox, {'status': 'answered'}, HTTP_HOST='a.example')
        self.assertNotContains(page, 'A one')

    def test_answer_notifies_the_author(self):
        feedback = Feedback.objects.create(user=self.author, site=self.site_a,
                                           text='Where is it?', kind='question')
        detail = reverse('gt_feedback_detail', args=[feedback.pk])
        # Reading is not answering.
        self.client.force_login(self.reader)
        self.assertEqual(self.client.post(detail, {'answer-status': 'closed'},
                                          HTTP_HOST='a.example').status_code, 404)
        self.client.force_login(self.reviewer)
        response = self.client.post(detail, {'answer-status': 'reviewing',
                                             'answer-response': 'In the menu.'},
                                    HTTP_HOST='a.example')
        self.assertEqual(response.status_code, 302)
        feedback.refresh_from_db()
        self.assertEqual((feedback.status, feedback.response, feedback.responded_by),
                         ('answered', 'In the menu.', self.reviewer))
        notification = Notification.objects.get(user=self.author)
        self.assertIn('Where is it?', notification.description)
        self.assertTrue(notification.link.endswith(detail))
        # Changing only the status notifies nobody again.
        self.client.post(detail, {'answer-status': 'closed',
                                  'answer-response': 'In the menu.'},
                         HTTP_HOST='a.example')
        self.assertEqual(Notification.objects.filter(user=self.author).count(), 1)
        self.client.force_login(self.author)
        self.assertContains(self.client.get(detail, HTTP_HOST='a.example'),
                            'In the menu.')

    def test_turned_off_by_site(self):
        set_settings('feedback_enabled', 'false', site=self.site_b)
        self.assertIn('gt-feedback-modal', self.button(self.author, 'a.example'))
        self.assertNotIn('gt-feedback-modal', self.button(self.author, 'b.example'))
        self.client.force_login(self.author)
        self.assertEqual(self.send(host='b.example').status_code, 404)
        self.assertEqual(self.send(host='a.example').status_code, 200)
        # Globally off, a Site turns it back on.
        set_settings('feedback_enabled', 'false')
        set_settings('feedback_enabled', 'true', site=self.site_a)
        self.assertIn('gt-feedback-modal', self.button(self.author, 'a.example'))
        self.assertNotIn('gt-feedback-modal', self.button(self.author, 'nowhere'))

    def test_off_without_the_setting_or_the_user(self):
        self.assertNotIn('gt-feedback-modal', self.button(AnonymousUser()))
        with self.settings(GT_FEEDBACK=False):
            self.assertNotIn('gt-feedback-modal', self.button(self.author))
            self.client.force_login(self.author)
            self.assertEqual(self.send().status_code, 404)


# -- choices of a relation by Site --------------------------------------------------

NEWHIRE_FORM = {'hire': {'model': 'demoapp.NewHire',
                         'fields': ['name', 'email', 'start_date', 'department']}}
HIRE_PERMS = ['demoapp.%s_newhire' % action
              for action in ('view', 'add', 'change', 'delete')]


class W32DepartmentLookup(BaseSelect2View):
    model = Department
    fields = ['name']


@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS,
                   ALLOWED_HOSTS=['*'])
class W32SiteChoicesTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        Site.objects.clear_cache()
        expose(Department, site_field='site')
        expose(NewHire)
        self.site_a = Site.objects.create(domain='a.example', name='A')
        self.site_b = Site.objects.create(domain='b.example', name='B')
        self.grant(*HIRE_PERMS)
        self.mine = Department.objects.create(name='Mine', site=self.site_a)
        self.theirs = Department.objects.create(name='Theirs', site=self.site_b)
        self.shared = Department.objects.create(name='Shared')

    def options(self, html):
        return sorted(name for name in ('Mine', 'Theirs', 'Shared')
                      if '>%s</option>' % name in html)

    def test_expose_checks_the_field(self):
        self.assertEqual(site_field_of(Department), 'site')
        self.assertEqual(site_field_of(NewHire), '')
        with self.assertRaises(ImproperlyConfigured):
            expose(Department, site_field='name')
        with self.assertRaises(ImproperlyConfigured):
            expose(Department, site_field='nothing')
        self.assertEqual(sorted(site_choices(Department.objects.all(), self.site_a)
                                .values_list('name', flat=True)), ['Mine', 'Shared'])

    def test_object_management_form_and_api(self):
        page = self.publish(design(node('object_management', 'hires', {
            'model': 'demoapp.NewHire', 'form': 'hire'}), forms=NEWHIRE_FORM),
            path='w32-hires')
        html = self.client.get(reverse('gt-design-page', args=['w32-hires']),
                               HTTP_HOST='a.example').content.decode()
        self.assertEqual(self.options(html), ['Mine', 'Shared'])
        url = self.api(page, 'hires')
        data = {'name': 'Eva', 'email': 'eva@example.com', 'start_date': '2026-01-05'}
        response = self.client.post(url, json.dumps(dict(data,
                                                         department=self.theirs.pk)),
                                    content_type='application/json',
                                    HTTP_HOST='a.example')
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('department', response.json())
        response = self.client.post(url, json.dumps(dict(data,
                                                         department=self.mine.pk)),
                                    content_type='application/json',
                                    HTTP_HOST='a.example')
        self.assertEqual(response.status_code, 201, response.content)
        # On the other Site, the other way round.
        response = self.client.post(url, json.dumps(dict(data, name='Leo',
                                                         department=self.mine.pk)),
                                    content_type='application/json',
                                    HTTP_HOST='b.example')
        self.assertEqual(response.status_code, 400, response.content)

    def test_crud_classic_form(self):
        page = self.publish(design(node('crud_classic', 'hires', {
            'model': 'demoapp.NewHire', 'form': 'hire'}), forms=NEWHIRE_FORM),
            path='w32-crud-hires')
        base = self.api(page, 'hires')
        html = self.client.get(base + 'create/', HTTP_HOST='a.example').content.decode()
        self.assertEqual(self.options(html), ['Mine', 'Shared'])
        response = self.client.post(base + 'create/', {
            'name': 'Eva', 'email': 'eva@example.com', 'start_date': '2026-01-05',
            'department': self.theirs.pk}, HTTP_HOST='a.example')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(NewHire.objects.filter(name='Eva').exists())

    def test_grid_batch(self):
        page = self.publish(design(node('interactive_grid', 'grid', {
            'model': 'demoapp.NewHire',
            'columns': ['name', 'email', 'start_date', 'department'],
            'editable': ['name', 'email', 'start_date', 'department']})),
            path='w32-grid-hires')
        url = self.api(page, 'grid')

        def save(department):
            return self.client.post(url + 'save/', json.dumps({'rows': [{
                'key': 'n1', 'op': 'create', 'data': {
                    'name': 'Eva', 'email': 'eva@example.com',
                    'start_date': '2026-01-05', 'department': department}}]}),
                content_type='application/json', HTTP_HOST='a.example')

        response = save(self.theirs.pk)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(NewHire.objects.exists())
        response = save(self.shared.pk)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(NewHire.objects.get().department, self.shared)
        html = self.client.get(reverse('gt-design-page', args=['w32-grid-hires']),
                               HTTP_HOST='a.example').content.decode()
        self.assertNotIn('>Theirs</option>', html)

    def test_lookup(self):
        view = W32DepartmentLookup.as_view({'get': 'list'})
        response = view(APIRequestFactory().get('/', HTTP_HOST='a.example'))
        self.assertEqual(sorted(item['text'] for item in response.data['results']),
                         ['Mine', 'Shared'])
        # A lookup that says it is not by Site lists them all.
        everything = type('Everything', (W32DepartmentLookup,), {'site_field': ''})
        response = everything.as_view({'get': 'list'})(
            APIRequestFactory().get('/', {'page': 1}, HTTP_HOST='a.example'))
        self.assertEqual(response.data['total_count'], 3)
        expose(Department)
        response = view(APIRequestFactory().get('/', HTTP_HOST='a.example'))
        self.assertEqual(response.data['total_count'], 3)
