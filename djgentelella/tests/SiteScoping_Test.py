"""Menus and settings scoped by Site."""

import os
from importlib import import_module
from io import StringIO
from tempfile import TemporaryDirectory
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sites.models import Site
from django.contrib.sites.requests import RequestSite
from django.core.cache import cache
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.template import Context, Template
from django.test import RequestFactory, TestCase, override_settings

from djgentelella import sites as gt_sites
from djgentelella.checks import check_sites_installed
from djgentelella.admin import GentelellaSettingsAdmin, MenuAdmin
from djgentelella.models import GentelellaSettings, MenuItem
from djgentelella.sites import get_current_site, site_pk, site_q
from djgentelella.templatetags.gentelellamenu import scope_menu_items
from djgentelella.utils import clean_cache, get_settings, set_settings

HOSTS = ['testserver', 'a.test', 'b.test', 'nosite.test']


def make_request(host='testserver', **attrs):
    request = RequestFactory().get('/', HTTP_HOST=host)
    request.user = AnonymousUser()
    for name, value in attrs.items():
        setattr(request, name, value)
    return request


@override_settings(ALLOWED_HOSTS=HOSTS)
class CurrentSiteTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.site_a = Site.objects.create(domain='a.test', name='A')

    def test_none_without_request(self):
        self.assertIsNone(get_current_site())
        self.assertIsNone(get_current_site(None))

    def test_none_without_a_site_for_the_host(self):
        # testserver is not a Site; SITE_ID is not a fallback.
        self.assertIsNone(get_current_site(make_request()))
        self.assertIsNone(get_current_site(make_request('nosite.test')))

    def test_site_by_host(self):
        self.assertEqual(get_current_site(make_request('a.test')), self.site_a)

    def test_site_by_host_without_the_port(self):
        self.assertEqual(get_current_site(make_request('a.test:8000')),
                         self.site_a)

    def test_host_is_case_insensitive(self):
        self.assertEqual(get_current_site(make_request('A.TEST')), self.site_a)

    def test_request_site_wins(self):
        site_b = Site.objects.create(domain='b.test', name='B')
        request = make_request('a.test', site=site_b)
        self.assertEqual(get_current_site(request), site_b)

    def test_request_site_none_is_global(self):
        request = make_request('a.test', site=None)
        self.assertIsNone(get_current_site(request))

    def test_request_site_that_is_not_a_row_is_global(self):
        request = make_request('a.test')
        request.site = RequestSite(request)
        self.assertIsNone(get_current_site(request))

    def test_resolved_once_per_request(self):
        request = make_request('a.test')
        get_current_site(request)
        with self.assertNumQueries(0):
            self.assertEqual(get_current_site(request), self.site_a)

    def test_none_when_sites_is_not_installed(self):
        with mock.patch.object(gt_sites.apps, 'is_installed', return_value=False):
            self.assertIsNone(get_current_site(make_request('a.test')))
            self.assertFalse(gt_sites.sites_installed())

    def test_site_q(self):
        self.assertEqual(site_q(None), site_q(None, field='site'))
        self.assertEqual(str(site_q(None)), "(AND: ('site__isnull', True))")
        self.assertIn("('site', ", str(site_q(self.site_a)))
        self.assertIn("('page__site__isnull', True)",
                      str(site_q(self.site_a, field='page__site')))

    def test_site_q_filters(self):
        mine = MenuItem.objects.create(title='A', url_name='a', site=self.site_a)
        other = MenuItem.objects.create(
            title='B', url_name='b',
            site=Site.objects.create(domain='b.test', name='B'))
        glob = MenuItem.objects.create(title='G', url_name='g')
        self.assertEqual(set(MenuItem.objects.filter(site_q(self.site_a))),
                         {mine, glob})
        self.assertEqual(set(MenuItem.objects.filter(site_q(None))), {glob})
        self.assertNotIn(other, MenuItem.objects.filter(site_q(self.site_a)))


class SitePkTest(TestCase):

    def test_site_and_ids(self):
        site = Site.objects.create(domain='pk.test', name='PK')
        self.assertIsNone(site_pk(None))
        self.assertEqual(site_pk(site), site.pk)
        self.assertEqual(site_pk(site.pk), site.pk)
        self.assertEqual(site_pk(str(site.pk)), site.pk)

    def test_request_site_is_global(self):
        request_site = RequestSite(make_request())
        self.assertIsNone(site_pk(request_site))
        set_settings('scoped_rs', 'Global')
        cache.clear()
        self.assertEqual(get_settings('scoped_rs', site=request_site), 'Global')

    def test_invalid_values_fail_clearly(self):
        with self.assertRaisesMessage(ValueError, 'is not a Site id'):
            site_pk('example.com')
        with self.assertRaisesMessage(ValueError, 'has not been saved'):
            site_pk(Site(domain='unsaved.test', name='U'))
        for value in (True, 1.5, object()):
            with self.subTest(value=value), self.assertRaises(TypeError):
                site_pk(value)
        with self.assertRaisesMessage(ValueError, 'is not a Site id'):
            set_settings('scoped_bad', 'v', site='example.com')
        with self.assertRaisesMessage(ValueError, 'is not a Site id'):
            get_settings('scoped_bad', site='example.com')


class SitesRequiredTest(TestCase):

    def test_no_error_with_sites_installed(self):
        self.assertEqual(check_sites_installed(), [])

    def test_error_without_sites(self):
        with mock.patch('djgentelella.checks.apps.is_installed',
                        return_value=False):
            errors = check_sites_installed()
        self.assertEqual([e.id for e in errors], ['djgentelella.E001'])
        self.assertIn('django.contrib.sites', errors[0].hint)

    def test_migration_refuses_duplicates_and_deletes_nothing(self):
        migration = import_module('djgentelella.migrations.0022_site_scoping')
        model = mock.MagicMock()
        model.objects.order_by.return_value.values_list.return_value = [
            (1, 'k', 'first'), (2, 'k', 'second'), (3, 'other', 'x')]
        fake_apps = mock.Mock(get_model=mock.Mock(return_value=model))
        with self.assertRaises(migration.DuplicateGlobalSettings) as raised:
            migration.check_duplicate_global_settings(fake_apps, None)
        model.objects.filter.assert_not_called()
        self.assertIn("key='k': pk=1 value='first', pk=2 value='second'",
                      str(raised.exception))
        self.assertNotIn("key='other'", str(raised.exception))

    def test_migration_is_silent_without_duplicates(self):
        migration = import_module('djgentelella.migrations.0022_site_scoping')
        model = mock.MagicMock()
        model.objects.order_by.return_value.values_list.return_value = [
            (1, 'k', 'v')]
        out = StringIO()
        with mock.patch('sys.stdout', out):
            migration.check_duplicate_global_settings(
                mock.Mock(get_model=mock.Mock(return_value=model)), None)
        model.objects.filter.assert_not_called()
        self.assertEqual(out.getvalue(), '')


@override_settings(ALLOWED_HOSTS=HOSTS)
class SiteMenuTest(TestCase):
    """Two Sites, a global menu and items of each Site."""

    @classmethod
    def setUpTestData(cls):
        cls.site_a = Site.objects.create(domain='a.test', name='A')
        cls.site_b = Site.objects.create(domain='b.test', name='B')
        cls.home = MenuItem.objects.create(
            title='Global home', url_name='/home', category='main', position=0)
        cls.reports = MenuItem.objects.create(
            title='Global reports', url_name='/reports', category='main',
            position=1)
        MenuItem.objects.create(
            title='Global child', url_name='/reports/all', category='main',
            parent=cls.reports)
        MenuItem.objects.create(
            title='Child of B', url_name='/reports/b', category='main',
            parent=cls.reports, site=cls.site_b)
        cls.only_a = MenuItem.objects.create(
            title='Only on A', url_name='/a', category='main', position=2,
            site=cls.site_a)
        # Same url_name and category as "Global home": replaces it on A.
        cls.home_a = MenuItem.objects.create(
            title='Home of A', url_name='/home', category='main', position=0,
            site=cls.site_a)
        MenuItem.objects.create(
            title='Sidebar global', url_name='/side', category='sidebar')
        MenuItem.objects.create(
            title='Sidebar B', url_name='/side-b', category='sidebar',
            site=cls.site_b)
        MenuItem.objects.create(
            title='Footer A', url_name='/foot-a', category='sidebarfooter',
            icon='fa fa-cog', site=cls.site_a)

    def render(self, tag, host):
        template = Template('{% load gentelellamenu %}{% ' + tag + ' %}')
        return template.render(Context({'request': make_request(host)}))

    def test_without_site_only_global(self):
        html = self.render('top_menu', 'testserver')
        self.assertIn('Global home', html)
        self.assertIn('Global reports', html)
        self.assertIn('Global child', html)
        self.assertNotIn('Only on A', html)
        self.assertNotIn('Home of A', html)
        self.assertNotIn('Child of B', html)

    def test_global_and_site_menu(self):
        html = self.render('top_menu', 'a.test')
        self.assertIn('Global reports', html)
        self.assertIn('Global child', html)
        self.assertIn('Only on A', html)
        html = self.render('top_menu', 'b.test')
        self.assertIn('Global reports', html)
        self.assertNotIn('Only on A', html)

    def test_child_of_another_site_is_hidden_under_a_global_parent(self):
        self.assertNotIn('Child of B', self.render('top_menu', 'a.test'))
        self.assertIn('Child of B', self.render('top_menu', 'b.test'))

    def test_hidden_children_do_not_make_a_dropdown(self):
        lonely = MenuItem.objects.create(
            title='Lonely', url_name='/lonely', category='main', position=5)
        MenuItem.objects.create(
            title='Hidden child', url_name='/lonely/b', category='main',
            parent=lonely, site=self.site_b)
        html = self.render('top_menu', 'a.test')
        self.assertNotIn('id="m_%d"' % lonely.pk, html)
        self.assertIn('id="m_%d"' % lonely.pk, self.render('top_menu', 'b.test'))

    def test_site_item_overrides_the_global_one(self):
        html = self.render('top_menu', 'a.test')
        self.assertIn('Home of A', html)
        self.assertNotIn('Global home', html)
        html = self.render('top_menu', 'b.test')
        self.assertIn('Global home', html)
        self.assertNotIn('Home of A', html)

    def test_override_keeps_the_position(self):
        items = scope_menu_items(
            MenuItem.objects.filter(parent=None, category='main').order_by(
                'position'), self.site_a)
        self.assertEqual([i.title for i in items],
                         ['Home of A', 'Global reports', 'Only on A'])

    def test_placeholder_url_name_overrides_only_the_same_title(self):
        # Like demomenu: several dropdown roots, all with url_name='/'.
        for position, title in enumerate(['Base 1', 'Base 2', 'Base 3'], 10):
            MenuItem.objects.create(title=title, url_name='/', category='main',
                                    position=position)
        MenuItem.objects.create(title='Base 2', url_name='/', category='main',
                                position=11, site=self.site_a, icon='fa fa-a')
        MenuItem.objects.create(title='Extra of A', url_name='#',
                                category='main', position=13, site=self.site_a)
        items = scope_menu_items(
            MenuItem.objects.filter(parent=None, category='main',
                                    position__gte=10).order_by('position'),
            self.site_a)
        self.assertEqual([(i.title, i.site_id) for i in items], [
            ('Base 1', None), ('Base 2', self.site_a.pk), ('Base 3', None),
            ('Extra of A', self.site_a.pk)])

    def test_override_only_in_the_same_category(self):
        MenuItem.objects.create(
            title='Sidebar home', url_name='/home', category='sidebar')
        html = self.render('sidebar_menu', 'a.test')
        self.assertIn('Sidebar home', html)

    def test_sidebar(self):
        self.assertNotIn('Sidebar B', self.render('sidebar_menu', 'a.test'))
        html = self.render('sidebar_menu', 'b.test')
        self.assertIn('Sidebar B', html)
        self.assertIn('Sidebar global', html)

    def test_footer(self):
        self.assertIn('/foot-a', self.render('footer_sidebar_menu', 'a.test'))
        self.assertNotIn('/foot-a', self.render('footer_sidebar_menu', 'b.test'))

    def test_request_site_from_middleware(self):
        template = Template('{% load gentelellamenu %}{% top_menu %}')
        request = make_request('testserver', site=self.site_a)
        self.assertIn('Only on A', template.render(Context({'request': request})))


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
    'LOCATION': 'gt_cache_table_never_created'}})
class SettingsWithoutCacheTableTest(TestCase):
    """A DatabaseCache whose table was not created -- a test database, where
    nobody runs createcachetable -- must not break saving a setting (a fixture
    load), nor leave the surrounding transaction unusable."""

    def test_save_and_delete_survive_a_missing_cache_table(self):
        with self.assertLogs('djgentelella.models', 'WARNING'):
            with transaction.atomic():
                row = GentelellaSettings.objects.create(key='no_table', value='1')
                row.value = '2'
                row.save()
                # Still usable after the failed cache query.
                self.assertEqual(GentelellaSettings.objects.get(pk=row.pk).value, '2')
                row.delete()
        self.assertFalse(GentelellaSettings.objects.filter(key='no_table').exists())

    def test_loaddata_with_settings(self):
        fixture = ('[{"model": "djgentelella.gentelellasettings", "pk": 9001, '
                   '"fields": {"key": "from_fixture", "value": "x"}}]')
        path = os.path.join(self.enterContext(TemporaryDirectory()), 'settings.json')
        with open(path, 'w') as handle:
            handle.write(fixture)
        with self.assertLogs('djgentelella.models', 'WARNING'):
            call_command('loaddata', path, verbosity=0)
        self.assertEqual(GentelellaSettings.objects.get(pk=9001).value, 'x')


@override_settings(ALLOWED_HOSTS=HOSTS)
class SiteSettingsTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.site_a = Site.objects.create(domain='a.test', name='A')
        cls.site_b = Site.objects.create(domain='b.test', name='B')

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_global_signature_still_works(self):
        set_settings('scoped_title', 'Global')
        self.assertEqual(get_settings('scoped_title'), 'Global')
        self.assertEqual(get_settings('scoped_missing'), '')
        self.assertIsNone(get_settings('scoped_missing', none_asdefault=True))
        # get_settings(key, none_asdefault) was the old positional form.
        self.assertIsNone(get_settings('scoped_missing', True))

    def test_global_vs_site(self):
        set_settings('scoped_title', 'Global')
        set_settings('scoped_title', 'Of A', site=self.site_a)
        self.assertEqual(get_settings('scoped_title'), 'Global')
        self.assertEqual(get_settings('scoped_title', self.site_a), 'Of A')
        self.assertEqual(get_settings('scoped_title', site=self.site_a.pk), 'Of A')
        # B has no value of its own: the global one.
        self.assertEqual(get_settings('scoped_title', site=self.site_b), 'Global')
        self.assertEqual(GentelellaSettings.objects.filter(key='scoped_title').count(),
                         2)

    def test_site_value_without_global(self):
        set_settings('scoped_only_a', 'A', site=self.site_a)
        self.assertEqual(get_settings('scoped_only_a', site=self.site_a), 'A')
        self.assertEqual(get_settings('scoped_only_a'), '')
        self.assertIsNone(get_settings('scoped_only_a', site=self.site_b,
                                       none_asdefault=True))

    def test_empty_site_value_still_overrides(self):
        set_settings('scoped_title', 'Global')
        set_settings('scoped_title', '', site=self.site_a)
        self.assertEqual(get_settings('scoped_title', site=self.site_a), '')

    def test_set_settings_updates_in_place(self):
        set_settings('scoped_title', 'one', site=self.site_a)
        set_settings('scoped_title', 'two', site=self.site_a)
        self.assertEqual(get_settings('scoped_title', site=self.site_a), 'two')
        self.assertEqual(GentelellaSettings.objects.filter(key='scoped_title').count(),
                         1)

    def test_cache_per_key_and_site(self):
        set_settings('scoped_title', 'Global')
        set_settings('scoped_title', 'Of A', site=self.site_a)
        get_settings('scoped_title')
        get_settings('scoped_title', site=self.site_a)
        get_settings('scoped_title', site=self.site_b)
        with self.assertNumQueries(0):
            self.assertEqual(get_settings('scoped_title'), 'Global')
            self.assertEqual(get_settings('scoped_title', site=self.site_a), 'Of A')
            self.assertEqual(get_settings('scoped_title', site=self.site_b), 'Global')

    def test_setting_a_site_does_not_touch_the_global_cache(self):
        set_settings('scoped_title', 'Global')
        set_settings('scoped_title', 'Of A', site=self.site_a)
        get_settings('scoped_title')
        get_settings('scoped_title', site=self.site_a)
        set_settings('scoped_title', 'New A', site=self.site_a)
        with self.assertNumQueries(0):
            self.assertEqual(get_settings('scoped_title'), 'Global')
        self.assertEqual(get_settings('scoped_title', site=self.site_a), 'New A')

    def test_changing_the_global_reaches_sites_without_their_own(self):
        set_settings('scoped_title', 'Global')
        self.assertEqual(get_settings('scoped_title', site=self.site_b), 'Global')
        set_settings('scoped_title', 'New global')
        self.assertEqual(get_settings('scoped_title', site=self.site_b), 'New global')

    def test_new_site_value_is_seen_after_a_miss(self):
        set_settings('scoped_title', 'Global')
        self.assertEqual(get_settings('scoped_title', site=self.site_a), 'Global')
        # An ORM write, not set_settings: the cached "A has none" goes too.
        GentelellaSettings.objects.create(
            key='scoped_title', value='Of A', site=self.site_a)
        self.assertEqual(get_settings('scoped_title', site=self.site_a), 'Of A')

    def test_orm_save_and_delete_invalidate(self):
        set_settings('scoped_title', 'Of A', site=self.site_a)
        self.assertEqual(get_settings('scoped_title', site=self.site_a), 'Of A')
        row = GentelellaSettings.objects.get(key='scoped_title', site=self.site_a)
        row.value = 'Edited'
        row.save()
        self.assertEqual(get_settings('scoped_title', site=self.site_a), 'Edited')
        row.delete()
        self.assertEqual(get_settings('scoped_title', site=self.site_a), '')

    def test_moving_a_row_to_another_site_forgets_the_old_scope(self):
        set_settings('scoped_move', 'G')
        set_settings('scoped_move', 'VA', site=self.site_a)
        self.assertEqual(get_settings('scoped_move', site=self.site_a), 'VA')
        self.assertEqual(get_settings('scoped_move', site=self.site_b), 'G')
        row = GentelellaSettings.objects.get(key='scoped_move', site=self.site_a)
        row.site = self.site_b
        row.save()
        self.assertEqual(get_settings('scoped_move', site=self.site_a), 'G')
        self.assertEqual(get_settings('scoped_move', site=self.site_b), 'VA')

    def test_moving_a_row_to_global_and_back(self):
        set_settings('scoped_move', 'VA', site=self.site_a)
        self.assertEqual(get_settings('scoped_move', site=self.site_a), 'VA')
        self.assertEqual(get_settings('scoped_move'), '')
        row = GentelellaSettings.objects.get(key='scoped_move')
        row.site = None
        row.save()
        self.assertEqual(get_settings('scoped_move'), 'VA')
        row.site = self.site_b
        row.save()
        self.assertEqual(get_settings('scoped_move'), '')
        self.assertEqual(get_settings('scoped_move', site=self.site_b), 'VA')

    def test_renaming_the_key_forgets_the_old_one(self):
        set_settings('scoped_old', 'V', site=self.site_a)
        self.assertEqual(get_settings('scoped_old', site=self.site_a), 'V')
        row = GentelellaSettings.objects.get(key='scoped_old')
        row.key = 'scoped_new'
        row.save()
        self.assertEqual(get_settings('scoped_old', site=self.site_a), '')
        self.assertEqual(get_settings('scoped_new', site=self.site_a), 'V')

    def test_moving_a_row_in_the_admin(self):
        admin = get_user_model().objects.create_superuser(
            'scopedmover', 'scopedmover@example.com', 'secret')
        self.client.force_login(admin)
        set_settings('scoped_move', 'G')
        set_settings('scoped_move', 'VA', site=self.site_a)
        self.assertEqual(get_settings('scoped_move', site=self.site_a), 'VA')
        row = GentelellaSettings.objects.get(key='scoped_move', site=self.site_a)
        response = self.client.post(
            '/admin/djgentelella/gentelellasettings/%d/change/' % row.pk,
            {'key': 'scoped_move', 'value': 'VA', 'site': self.site_b.pk})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(get_settings('scoped_move', site=self.site_a), 'G')
        self.assertEqual(get_settings('scoped_move', site=self.site_b), 'VA')

    def test_clean_cache_per_site(self):
        set_settings('scoped_title', 'Of A', site=self.site_a)
        get_settings('scoped_title', site=self.site_a)
        GentelellaSettings.objects.filter(key='scoped_title').update(value='Raw')
        self.assertEqual(get_settings('scoped_title', site=self.site_a), 'Of A')
        clean_cache(['scoped_title'], site=self.site_a)
        self.assertEqual(get_settings('scoped_title', site=self.site_a), 'Raw')

    def test_unique_key_per_site(self):
        GentelellaSettings.objects.create(key='scoped_u', value='g')
        GentelellaSettings.objects.create(key='scoped_u', value='a', site=self.site_a)
        GentelellaSettings.objects.create(key='scoped_u', value='b', site=self.site_b)
        with self.assertRaises(IntegrityError), transaction.atomic():
            GentelellaSettings.objects.create(
                key='scoped_u', value='a2', site=self.site_a)
        with self.assertRaises(IntegrityError), transaction.atomic():
            GentelellaSettings.objects.create(key='scoped_u', value='g2')

    def test_template_tag_uses_the_request_site(self):
        set_settings('scoped_title', 'Global')
        set_settings('scoped_title', 'Of A', site=self.site_a)
        template = Template("{% load gtsettings %}{% get_settings 'scoped_title' %}")
        for host, expected in (('a.test', 'Of A'), ('b.test', 'Global'),
                               ('testserver', 'Global')):
            context = Context({'request': make_request(host)})
            self.assertEqual(template.render(context), expected)

    def test_template_tag_without_request(self):
        set_settings('scoped_title', 'Global')
        template = Template("{% load gtsettings %}{% get_settings 'scoped_title' %}")
        self.assertEqual(template.render(Context({})), 'Global')


@override_settings(ALLOWED_HOSTS=HOSTS)
class SiteAdminTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.site_a = Site.objects.create(domain='a.test', name='A')
        cls.admin = get_user_model().objects.create_superuser(
            'scopedadmin', 'scopedadmin@example.com', 'secret')

    def setUp(self):
        cache.clear()
        self.client.force_login(self.admin)

    def test_site_filter_and_column(self):
        self.assertIn('site', MenuAdmin.list_filter)
        self.assertIn('site', GentelellaSettingsAdmin.list_filter)
        self.assertIn('site', GentelellaSettingsAdmin.list_display)

    def test_menu_changelist_filters_by_site(self):
        MenuItem.objects.create(title='menu global', url_name='/g')
        MenuItem.objects.create(title='menu of A', url_name='/a', site=self.site_a)
        response = self.client.get(
            '/admin/djgentelella/menuitem/?site__id__exact=%d' % self.site_a.pk)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'menu of A')
        self.assertNotContains(response, 'menu global')

    def test_site_is_optional_in_the_add_form(self):
        response = self.client.post('/admin/djgentelella/gentelellasettings/add/',
                                    {'key': 'scoped_admin', 'value': 'v', 'site': ''})
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(GentelellaSettings.objects.get(key='scoped_admin').site)

    def test_duplicate_global_key_is_a_form_error(self):
        GentelellaSettings.objects.create(key='scoped_admin', value='v')
        response = self.client.post('/admin/djgentelella/gentelellasettings/add/',
                                    {'key': 'scoped_admin', 'value': 'w', 'site': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            GentelellaSettings.objects.filter(key='scoped_admin').count(), 1)

    def test_clean_settings_cache_action(self):
        set_settings('scoped_title', 'Of A', site=self.site_a)
        get_settings('scoped_title', site=self.site_a)
        GentelellaSettings.objects.filter(key='scoped_title').update(value='Raw')
        row = GentelellaSettings.objects.get(key='scoped_title')
        self.client.post('/admin/djgentelella/gentelellasettings/', {
            'action': 'clean_settings_cache', '_selected_action': [row.pk]})
        self.assertEqual(get_settings('scoped_title', site=self.site_a), 'Raw')


class DemoMenuWithSiteTest(TestCase):

    def setUp(self):
        cache.clear()

    def test_global_only_by_default(self):
        call_command('demomenu', stdout=StringIO())
        self.assertTrue(MenuItem.objects.filter(title='Icons').exists())
        self.assertFalse(MenuItem.objects.filter(site__isnull=False).exists())

    def test_with_site(self):
        call_command('demomenu', '--with-site', '--site-domain', 'demo2.test',
                     stdout=StringIO())
        call_command('demomenu', '--with-site', '--site-domain', 'demo2.test',
                     stdout=StringIO())
        site = Site.objects.get(domain='demo2.test')
        self.assertTrue(MenuItem.objects.filter(
            title='Icons', site__isnull=True).exists())
        self.assertEqual(
            set(MenuItem.objects.filter(site=site).values_list('title', flat=True)),
            {'Site 2 home', 'Icons (site 2)', 'Font Awesome'})
        self.assertEqual(get_settings('sidebar_title', site=site), 'Demo site 2')
