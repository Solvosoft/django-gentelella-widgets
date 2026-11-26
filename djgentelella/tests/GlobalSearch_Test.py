"""djgentelella.search: the searchable sources, the engines, the page, the
JSON API and the box of the top bar. Runs on SQLite (icontains) and on
PostgreSQL (full-text, and trigram when pg_trgm is installed)."""
import datetime
from unittest import mock, skipUnless

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.template import Context, Template
from django.test import RequestFactory, TestCase, override_settings, tag
from django.urls import reverse
from django.utils import timezone, translation

from demoapp import models as demo
from djgentelella.datasources.base import (
    FunctionDataSource, ModelDataSource, register_datasource,
    unregister_datasource,
)
from djgentelella.models import GentelellaSettings, MenuItem
from djgentelella.search import (
    GlobalSearch, reset_trigram_cache, search, searchable, searchable_sources,
    trigram_available,
)
from djgentelella.search import engine
from djgentelella.search.base import build_url, render_text, safe_url
from djgentelella.search.views import navbar_enabled

User = get_user_model()

IS_POSTGRES = (connection.vendor == 'postgresql'
               and apps.is_installed('django.contrib.postgres'))


def person(name, country):
    return demo.Person.objects.create(
        name=name, country=country, born_date=datetime.date(1990, 1, 1),
        last_time=timezone.make_aware(datetime.datetime(2020, 1, 1)))


class CountrySource(ModelDataSource):
    model = demo.Country
    name = 'test.search.countries'
    label = 'Test countries'
    fields = ['id', 'name', 'code']
    global_search = GlobalSearch(
        fields={'name': 'A', 'code': 'B'}, title='name', subtitle='{code}',
        url='demoapp_country_detail', group='Countries', icon='fa fa-flag')


@searchable(fields={'name': 'A', 'country__name': 'C'}, title='name',
            subtitle='country__name', url='demoapp_person_detail')
class PersonSource(ModelDataSource):
    model = demo.Person
    name = 'test.search.people'
    label = 'People'


SOURCES = [CountrySource.name, PersonSource.name]


class SearchFixture:

    @classmethod
    def setUpTestData(cls):
        cls.cr = demo.Country.objects.create(name='Costa Rica', code='cr')
        cls.pa = demo.Country.objects.create(name='Panama', code='pa')
        cls.ni = demo.Country.objects.create(name='Nicaragua', code='ni')
        cls.ana = person('Ana Rica', cls.pa)
        cls.beto = person('Beto Mora', cls.cr)
        cls.carla = person('Carla Panameña', cls.ni)
        cls.admin = User.objects.create_superuser('admin', 'a@example.com', 'x')
        cls.viewer = User.objects.create_user('viewer', 'v@example.com', 'x')
        cls.viewer.user_permissions.add(Permission.objects.get(
            codename='view_country', content_type__app_label='demoapp'))

    def setUp(self):
        translation.activate('en')
        self.addCleanup(translation.deactivate)
        for source in (CountrySource, PersonSource):
            register_datasource(source)
            self.addCleanup(unregister_datasource, source.name)
        # The detection of pg_trgm is cached per process; asked here once so
        # the query counts below only count the searches.
        trigram_available()

    def request(self, user=None, site=None, path='/'):
        request = RequestFactory().get(path)
        request.user = user if user is not None else self.admin
        if site is not None:
            request.site = site
        return request

    def titles(self, groups):
        return {group.source: [hit.title for hit in group.results]
                for group in groups}


class GlobalSearchSpecTest(TestCase):

    def test_weights_are_checked(self):
        with self.assertRaises(ImproperlyConfigured):
            GlobalSearch(fields={'name': 'E'})
        with self.assertRaises(ImproperlyConfigured):
            GlobalSearch(fields='name')
        with self.assertRaises(ImproperlyConfigured):
            GlobalSearch(limit=0)

    def test_fields_list_and_default(self):
        request = RequestFactory().get('/')
        source = ModelDataSource(demo.Country, name='x', perms=[])
        self.assertEqual(GlobalSearch(fields=['name', 'code'])
                         .weighted_fields(source, request),
                         [('name', 'A'), ('code', 'A')])
        # Without fields: the text columns of the source.
        self.assertEqual(GlobalSearch().weighted_fields(source, request),
                         [('name', 'A'), ('code', 'A')])

    def test_paths_must_exist_and_not_repeat_the_object(self):
        request = RequestFactory().get('/')
        source = ModelDataSource(demo.Country, name='x', perms=[])
        with self.assertRaises(ImproperlyConfigured):
            GlobalSearch(fields=['nope']).weighted_fields(source, request)
        # A reverse relation (or a many-to-many) would repeat the country.
        with self.assertRaises(ImproperlyConfigured):
            GlobalSearch(fields=['person__name']).weighted_fields(source, request)

    def test_titles(self):
        country = demo.Country(pk=7, name='Costa Rica', code='cr')
        someone = demo.Person(name='Ana', country=country)
        self.assertEqual(render_text('name', country), 'Costa Rica')
        self.assertEqual(render_text('{code} - {name}', country), 'cr - Costa Rica')
        self.assertEqual(render_text('{country.name}', someone), 'Costa Rica')
        self.assertEqual(render_text('{country__code}', someone), 'cr')
        self.assertEqual(render_text('country__name', someone), 'Costa Rica')
        self.assertEqual(render_text(lambda obj: obj.name.upper(), country),
                         'COSTA RICA')
        self.assertEqual(GlobalSearch().render_title(country), 'Costa Rica')
        self.assertEqual(GlobalSearch().render_subtitle(country), '')

    def test_urls(self):
        country = demo.Country(pk=7, name='Costa Rica', code='cr')
        self.assertEqual(build_url('demoapp_country_detail', country),
                         '/demoapp/country/7')
        self.assertEqual(build_url('/countries/{pk}/', country), '/countries/7/')
        self.assertEqual(build_url('page:clientes/ficha', country),
                         reverse('gt-design-page',
                                 kwargs={'path': 'clientes/ficha/7'}))
        self.assertEqual(build_url(lambda obj: '/x/%s' % obj.code, country), '/x/cr')
        self.assertIsNone(build_url('no-such-url-name', country))
        # No url and no get_absolute_url: a hit without a link.
        self.assertIsNone(build_url(None, country))

    def test_unsafe_urls_are_dropped(self):
        self.assertIsNone(safe_url('javascript:alert(1)'))
        self.assertIsNone(safe_url(' JaVa\tScRiPt:alert(1)'))
        self.assertIsNone(safe_url('data:text/html,x'))
        self.assertEqual(safe_url('/a/b?c=1'), '/a/b?c=1')
        self.assertEqual(safe_url('https://example.com/'), 'https://example.com/')
        self.assertIsNone(GlobalSearch(url='{name}').render_url(
            demo.Country(pk=1, name='javascript:alert(1)')))

    def test_title_relations_are_selected(self):
        spec = GlobalSearch(title='name', subtitle='{country__name}',
                            select_related=['country'])
        self.assertEqual(spec.related(demo.Person), ['country'])
        self.assertEqual(GlobalSearch(subtitle='country__name')
                         .related(demo.Person), ['country'])
        # Not a relation: nothing to select.
        self.assertEqual(GlobalSearch(title='name').related(demo.Person), [])

    def test_decorator_on_an_instance(self):
        source = searchable(fields=['name'])(
            ModelDataSource(demo.Country, name='x'))
        self.assertIsInstance(source.global_search, GlobalSearch)


class SearchTest(SearchFixture, TestCase):

    def test_two_sources_grouped_and_ordered_by_relevance(self):
        groups = search(self.request(), 'panama', sources=SOURCES)
        self.assertEqual([g.source for g in groups], SOURCES)
        # The country named so (a field weighted A) beats the person who
        # lives there (her country's name is weighted C).
        countries, people = groups
        self.assertEqual(countries.label, 'Countries')
        self.assertEqual(countries.icon, 'fa fa-flag')
        self.assertEqual([h.title for h in countries.results], ['Panama'])
        self.assertIn('Ana Rica', [h.title for h in people.results])
        self.assertGreater(countries.score, people.score)
        hit = countries.results[0]
        self.assertEqual((hit.subtitle, hit.url, hit.pk),
                         ('pa', '/demoapp/country/%s' % self.pa.pk, self.pa.pk))

    def test_results_ordered_by_relevance_inside_a_group(self):
        # "Rica" is in Ana's name (weight A) and in Beto's country (weight C).
        groups = search(self.request(), 'rica', sources=[PersonSource.name])
        self.assertEqual([h.title for h in groups[0].results][:2],
                         ['Ana Rica', 'Beto Mora'])
        scores = [h.score for h in groups[0].results]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(groups[0].results[1].subtitle, 'Costa Rica')

    def test_every_word_has_to_match(self):
        groups = search(self.request(), 'beto costa', sources=SOURCES)
        # Only Beto has both words (a trigram may still bring Costa Rica).
        self.assertEqual(self.titles(groups)[PersonSource.name], ['Beto Mora'])

    def test_limit_more_and_offset(self):
        for number in range(7):
            person('Zeta %d' % number, self.cr)
        groups = search(self.request(), 'zeta', sources=SOURCES, limit=5)
        self.assertEqual(len(groups[0].results), 5)
        self.assertTrue(groups[0].has_more)
        rest = search(self.request(), 'zeta', sources=SOURCES, limit=5, offset=5)
        self.assertEqual(len(rest[0].results), 2)
        self.assertFalse(rest[0].has_more)
        self.assertFalse({h.pk for h in groups[0].results}
                         & {h.pk for h in rest[0].results})
        # The source's own limit, else GT_SEARCH_LIMIT.
        with override_settings(GT_SEARCH_LIMIT=3):
            self.assertEqual(len(search(self.request(), 'zeta',
                                        sources=SOURCES)[0].results), 3)

    def test_one_query_per_source(self):
        request = self.request()
        with self.assertNumQueries(2):
            groups = search(request, 'rica', sources=SOURCES)
        self.assertEqual(len(groups), 2)
        # Titles and subtitles across a relation are loaded with the hits.
        with self.assertNumQueries(0):
            [(h.title, h.subtitle, h.url) for g in groups for h in g.results]

    def test_one_query_per_source_for_a_user_with_permissions(self):
        both = User.objects.create_user('both', 'b@example.com', 'x')
        both.user_permissions.add(*Permission.objects.filter(
            codename__in=['view_country', 'view_person']))
        request = self.request(both)
        request.user.has_perm('demoapp.view_country')  # loads its permissions
        with self.assertNumQueries(2):
            self.assertEqual(len(search(request, 'rica', sources=SOURCES)), 2)

    def test_short_text_costs_nothing(self):
        with self.assertNumQueries(0):
            self.assertEqual(search(self.request(), ' r ', sources=SOURCES), [])
            self.assertEqual(search(self.request(), '', sources=SOURCES), [])

    def test_a_source_without_permission_is_not_queried(self):
        request = self.request(self.viewer)
        with mock.patch.object(PersonSource, 'get_queryset',
                               autospec=True) as people:
            groups = search(request, 'rica', sources=SOURCES)
        people.assert_not_called()
        self.assertEqual([g.source for g in groups], [CountrySource.name])
        # Anonymous: no source asks for nobody (perms=None), nothing at all.
        anonymous = self.request(AnonymousUser())
        with self.assertNumQueries(0):
            self.assertEqual(search(anonymous, 'rica', sources=SOURCES), [])

    def test_a_row_the_user_cannot_see_does_not_appear(self):
        class OwnCountries(CountrySource):
            name = 'test.search.own'

            def get_queryset(self, request):
                # Row-level rule: this user only sees Costa Rica.
                return super().get_queryset(request).filter(code='cr')

        register_datasource(OwnCountries)
        self.addCleanup(unregister_datasource, OwnCountries.name)
        groups = search(self.request(), 'a', sources=[OwnCountries.name])
        self.assertEqual(groups, [])  # too short
        groups = search(self.request(), 'panama', sources=[OwnCountries.name])
        self.assertEqual(groups, [])
        groups = search(self.request(), 'costa', sources=[OwnCountries.name])
        self.assertEqual(self.titles(groups), {OwnCountries.name: ['Costa Rica']})

    def test_another_site_does_not_appear(self):
        here = Site.objects.create(domain='here.example.com', name='here')
        there = Site.objects.create(domain='there.example.com', name='there')
        for title, site in (('Menu here', here), ('Menu there', there),
                            ('Menu global', None)):
            MenuItem.objects.create(title=title, url_name='#', category='main',
                                    site=site)
        source = searchable(fields=['title'], title='title')(ModelDataSource(
            MenuItem, name='test.search.menus', site_field='site', perms=[]))
        register_datasource(source)
        self.addCleanup(unregister_datasource, source.name)
        groups = search(self.request(site=here), 'menu', sources=[source.name])
        self.assertEqual(sorted(self.titles(groups)[source.name]),
                         ['Menu global', 'Menu here'])
        groups = search(self.request(site=there), 'menu', sources=[source.name])
        self.assertEqual(sorted(self.titles(groups)[source.name]),
                         ['Menu global', 'Menu there'])

    def test_function_source_refusing_is_skipped(self):
        source = searchable(fields=['name'])(FunctionDataSource(
            lambda request: demo.Country.objects.all(), [], name='test.search.fn'))
        register_datasource(source)
        self.addCleanup(unregister_datasource, source.name)
        self.assertEqual(len(search(self.request(), 'panama',
                                    sources=[source.name])), 1)
        with mock.patch.object(source, 'has_permission', return_value=True), \
                mock.patch.object(FunctionDataSource, 'get_queryset',
                                  side_effect=engine.PermissionDenied):
            self.assertEqual(search(self.request(), 'panama',
                                    sources=[source.name]), [])

    def test_sources_registry(self):
        found = searchable_sources()
        self.assertIn(CountrySource.name, found)
        self.assertIn('demoapp.person', found)  # the demo's
        self.assertNotIn('demoapp.purchases', found)  # not searchable
        self.assertEqual(list(searchable_sources(['nope', PersonSource.name])),
                         [PersonSource.name])
        # Every searchable source by default (the demo's included).
        names = {g.source for g in search(self.request(), 'panama')}
        self.assertTrue({CountrySource.name, 'demoapp.country'} <= names)

    @override_settings(GT_SEARCH_SOURCES='djgentelella.tests.GlobalSearch_Test'
                                         '.only_countries')
    def test_sources_hook(self):
        names = {g.source for g in search(self.request(), 'panama')}
        self.assertEqual(names, {CountrySource.name})
        # An explicit list is not restricted by the hook in search() itself.
        names = {g.source for g in search(self.request(), 'panama',
                                          sources=SOURCES)}
        self.assertEqual(names, set(SOURCES))

    def test_text_is_never_sql(self):
        # %, _ and quotes are matched as the characters they are: no LIKE
        # wildcard, no quoting trouble.
        for name, code in (('Rate 100% sure', 'pc'), ('Snake__case', 'sc'),
                           ("O'Brien land", 'ob'), ('Rate 1000 sure', 'p0'),
                           ('SnakeXcase', 'sx'), ('OXBrien land', 'ox')):
            demo.Country.objects.create(name=name, code=code)
        for text, found in (('100%', ['Rate 100% sure']), ('e__c', ['Snake__case']),
                            ("O'B", ["O'Brien land"])):
            with self.subTest(text=text):
                groups = search(self.request(), text, sources=SOURCES)
                self.assertEqual(self.titles(groups), {CountrySource.name: found})
        for text in ("pa'; DROP TABLE demoapp_country; --", 'zz_qq:*&|!(',
                     '"unclosed', '\\'):
            with self.subTest(text=text):
                self.assertEqual(search(self.request(), text, sources=SOURCES), [])
        self.assertEqual(demo.Country.objects.count(), 9)

    @override_settings(GT_SEARCH_MAX_LENGTH=5)
    def test_text_is_cut(self):
        self.assertEqual(engine.clean_text('  panama   city '), 'panam')
        self.assertTrue(search(self.request(), 'panamaXXXX', sources=SOURCES))


def only_countries(request):
    return [CountrySource.name]


HOOK_CALLS = []


def every_source_counted(request):
    """A GT_SEARCH_SOURCES hook that leaves every source and counts its
    calls."""
    HOOK_CALLS.append(request)
    return None


class SearchViewsTest(SearchFixture, TestCase):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def api(self, **params):
        response = self.client.get(reverse('gt-search-api'), params)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_api(self):
        data = self.api(q='panama', sources=','.join(SOURCES))
        self.assertEqual(data['query'], 'panama')
        self.assertEqual([g['source'] for g in data['groups']], SOURCES)
        group = data['groups'][0]
        self.assertEqual(set(group), {'source', 'label', 'icon', 'has_more',
                                      'more_url', 'results'})
        self.assertEqual(group['results'][0]['title'], 'Panama')
        self.assertEqual(group['results'][0]['url'],
                         '/demoapp/country/%s' % self.pa.pk)
        self.assertEqual(set(group['results'][0]),
                         {'title', 'subtitle', 'url', 'score', 'pk'})
        self.assertEqual(group['more_url'], '%s?q=panama&source=%s' % (
            reverse('gt-search'), CountrySource.name))

    def test_api_limit_offset_and_bad_values(self):
        for number in range(4):
            person('Zeta %d' % number, self.cr)
        data = self.api(q='zeta', sources=PersonSource.name, limit=2)
        self.assertEqual(len(data['groups'][0]['results']), 2)
        self.assertTrue(data['groups'][0]['has_more'])
        data = self.api(q='zeta', sources=PersonSource.name, limit=2, offset=2)
        self.assertFalse(data['groups'][0]['has_more'])
        # Nonsense falls back to the defaults instead of failing.
        data = self.api(q='zeta', sources=PersonSource.name, limit='x',
                        offset='-3')
        self.assertEqual(len(data['groups'][0]['results']), 4)
        with override_settings(GT_SEARCH_MAX_LIMIT=1):
            data = self.api(q='zeta', sources=PersonSource.name, limit=500)
            self.assertEqual(len(data['groups'][0]['results']), 1)
        self.assertEqual(self.client.post(reverse('gt-search-api'),
                                          {'q': 'zeta'}).status_code, 405)

    def test_api_respects_permissions(self):
        self.client.force_login(self.viewer)
        data = self.api(q='rica', sources=','.join(SOURCES))
        self.assertEqual([g['source'] for g in data['groups']],
                         [CountrySource.name])
        self.client.logout()
        self.assertEqual(self.api(q='rica', sources=','.join(SOURCES))['groups'],
                         [])

    @override_settings(GT_SEARCH_SOURCES='djgentelella.tests.GlobalSearch_Test'
                                         '.only_countries')
    def test_views_stay_within_the_sources_hook(self):
        data = self.api(q='rica', sources=','.join(SOURCES))
        self.assertEqual([g['source'] for g in data['groups']],
                         [CountrySource.name])
        response = self.client.get(reverse('gt-search'),
                                   {'q': 'rica', 'source': PersonSource.name})
        self.assertNotContains(response, 'Ana Rica')

    @override_settings(GT_SEARCH_SOURCES='djgentelella.tests.GlobalSearch_Test'
                                         '.every_source_counted')
    def test_the_sources_hook_is_asked_once_per_request(self):
        for url, params in ((reverse('gt-search'), {'q': 'rica'}),
                            (reverse('gt-search-api'), {'q': 'rica'})):
            with self.subTest(url=url):
                HOOK_CALLS.clear()
                response = self.client.get(url, params)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(HOOK_CALLS), 1)

    def test_results_page(self):
        response = self.client.get(reverse('gt-search'), {'q': 'rica'})
        self.assertEqual(response.status_code, 200)
        groups = {g.source: g for g in response.context['groups']}
        self.assertIn(PersonSource.name, groups)
        self.assertContains(response, 'href="/demoapp/person/%s"' % self.ana.pk)
        self.assertContains(response, 'Ana Rica')
        self.assertContains(response, 'gt-search-group', count=len(groups))

    def test_see_more_pages_one_group(self):
        for number in range(25):
            person('Zeta %02d' % number, self.cr)
        response = self.client.get(reverse('gt-search'), {'q': 'zeta'})
        more = '%s?q=zeta&amp;source=%s' % (reverse('gt-search'), PersonSource.name)
        self.assertContains(response, more)
        response = self.client.get(reverse('gt-search'),
                                   {'q': 'zeta', 'source': PersonSource.name})
        self.assertEqual(len(response.context['groups'][0].results), 20)
        self.assertEqual(response.context['next_page'], 2)
        self.assertIsNone(response.context['previous_page'])
        self.assertContains(response, '<small>People</small>', html=False)
        response = self.client.get(reverse('gt-search'), {
            'q': 'zeta', 'source': PersonSource.name, 'page': 2})
        self.assertEqual(len(response.context['groups'][0].results), 5)
        self.assertIsNone(response.context['next_page'])
        self.assertEqual(response.context['previous_page'], 1)
        self.assertNotContains(response, 'gt-search-more')

    def test_page_escapes_the_text_and_explains_short_texts(self):
        response = self.client.get(reverse('gt-search'),
                                   {'q': '<script>alert(1)</script>'})
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, 'gt-search-empty')
        self.assertContains(self.client.get(reverse('gt-search'), {'q': 'a'}),
                            'gt-search-short')

    def test_page_in_spanish(self):
        with translation.override('es'):
            response = self.client.get(reverse('gt-search'), {'q': 'xyzzy'},
                                       HTTP_ACCEPT_LANGUAGE='es')
        self.assertContains(response, 'No se encontró nada para')


@override_settings(GT_SEARCH_NAVBAR=False)
class NavbarBoxTest(SearchFixture, TestCase):
    BOX = 'gt-global-search-form'

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)

    def render(self, request, force=False):
        template = Template('{% load gtsearch %}{% global_search_box'
                            + (' force=True' if force else '') + ' %}')
        return template.render(Context({'request': request}))

    def test_off_by_default(self):
        self.assertFalse(navbar_enabled(self.request()))
        self.assertNotIn(self.BOX, self.render(self.request()))
        self.assertIn(self.BOX, self.render(self.request(), force=True))
        self.client.force_login(self.admin)
        page = self.client.get(reverse('gt-search'), {'q': 'rica'})
        self.assertNotContains(page, self.BOX)

    @override_settings(GT_SEARCH_NAVBAR=True)
    def test_on_with_the_setting(self):
        html = self.render(self.request())
        self.assertIn(self.BOX, html)
        self.assertIn('data-api="%s"' % reverse('gt-search-api'), html)
        self.client.force_login(self.admin)
        page = self.client.get(reverse('gt-search'), {'q': 'rica'})
        # The top bar has it, with the text of the results page.
        self.assertContains(page, self.BOX)
        self.assertContains(page, 'value="rica"', count=2)

    def test_a_site_turns_it_on_or_off(self):
        site = Site.objects.create(domain='app.example.com', name='app')
        GentelellaSettings.objects.create(key='global_search', value='true',
                                          site=site)
        self.assertTrue(navbar_enabled(self.request(site=site)))
        self.assertFalse(navbar_enabled(self.request()))
        other = Site.objects.create(domain='other.example.com', name='other')
        GentelellaSettings.objects.create(key='global_search', value='false',
                                          site=other)
        with override_settings(GT_SEARCH_NAVBAR=True):
            self.assertFalse(navbar_enabled(self.request(site=other)))
            self.assertTrue(navbar_enabled(self.request()))

    def test_the_site_value_is_cached(self):
        site = Site.objects.create(domain='app.example.com', name='app')
        request = self.request(site=site)
        navbar_enabled(request)
        with self.assertNumQueries(0):
            navbar_enabled(self.request(site=site))


class TrigramCacheTest(TestCase):

    def test_detection_is_asked_once(self):
        reset_trigram_cache()
        self.addCleanup(reset_trigram_cache)
        expected = 1 if connection.vendor == 'postgresql' else 0
        with self.assertNumQueries(expected):
            trigram_available()
            trigram_available()
        with override_settings(GT_SEARCH_TRIGRAM=True), self.assertNumQueries(0):
            self.assertTrue(trigram_available())


@tag('postgresql')
@skipUnless(IS_POSTGRES, 'full-text search needs PostgreSQL and '
            'django.contrib.postgres')
class PostgresGlobalSearchTest(SearchFixture, TestCase):

    def test_full_text_with_stemming_and_prefixes(self):
        CountrySource.search_config = 'english'
        self.addCleanup(delattr, CountrySource, 'search_config')
        demo.Country.objects.create(name='Islands of apples', code='ap')
        with override_settings(GT_SEARCH_TRIGRAM=False):
            titles = self.titles(search(self.request(), 'apple',
                                        sources=[CountrySource.name]))
            self.assertEqual(titles, {CountrySource.name: ['Islands of apples']})
            # Plain words are prefixes: "nicar" while typing.
            self.assertEqual(self.titles(search(self.request(), 'nicar',
                                                sources=[CountrySource.name])),
                             {CountrySource.name: ['Nicaragua']})
            # Without pg_trgm a typo finds nothing.
            self.assertEqual(search(self.request(), 'nicaruga',
                                    sources=[CountrySource.name]), [])

    def test_icontains_mode_is_kept(self):
        CountrySource.search_mode = 'icontains'
        self.addCleanup(delattr, CountrySource, 'search_mode')
        # icontains finds the middle of a word, full-text does not.
        self.assertEqual(self.titles(search(self.request(), 'aragu',
                                            sources=[CountrySource.name])),
                         {CountrySource.name: ['Nicaragua']})

    def test_weights_order_full_text_hits(self):
        with override_settings(GT_SEARCH_TRIGRAM=False):
            groups = search(self.request(), 'rica', sources=[PersonSource.name])
        self.assertEqual([h.title for h in groups[0].results],
                         ['Ana Rica', 'Beto Mora'])


@tag('postgresql')
@skipUnless(IS_POSTGRES, 'trigram search needs PostgreSQL')
class TrigramSearchTest(SearchFixture, TestCase):

    def setUp(self):
        super().setUp()
        reset_trigram_cache()
        self.addCleanup(reset_trigram_cache)
        if not trigram_available():
            self.skipTest('the pg_trgm extension is not installed')

    def test_a_typo_still_finds(self):
        groups = search(self.request(), 'nicaruga', sources=SOURCES)
        self.assertEqual(self.titles(groups)[CountrySource.name], ['Nicaragua'])
        groups = search(self.request(), 'panamá', sources=[CountrySource.name])
        self.assertEqual(self.titles(groups)[CountrySource.name][0], 'Panama')

    def test_exact_hits_first_and_one_query_per_source(self):
        with self.assertNumQueries(2):
            groups = search(self.request(), 'panama', sources=SOURCES)
        countries = groups[0]
        self.assertEqual(countries.results[0].title, 'Panama')

    @override_settings(GT_SEARCH_TRIGRAM_THRESHOLD=0.99)
    def test_threshold(self):
        self.assertEqual(search(self.request(), 'nicaruga', sources=SOURCES), [])

    def test_api_json(self):
        self.client.force_login(self.admin)
        data = self.client.get(reverse('gt-search-api'), {
            'q': 'nicaruga', 'sources': CountrySource.name}).json()
        self.assertEqual(data['groups'][0]['results'][0]['title'], 'Nicaragua')
