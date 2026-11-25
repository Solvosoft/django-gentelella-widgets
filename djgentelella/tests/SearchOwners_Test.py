"""W21: who a searchable source belongs to (``GlobalSearch.owners`` and
``tags``), what a ``GT_SEARCH_SOURCES`` hook reads instead of an attribute
of its own; and the base template and context of the results page."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from demoapp import models as demo
from djgentelella.datasources.base import (
    ModelDataSource, register_datasource, unregister_datasource,
)
from djgentelella.search import (
    GlobalSearch, is_owned_by, searchable, searchable_sources, source_owners,
    source_tags,
)
from djgentelella.search.views import page_context

__all__ = ['SearchOwnersTest', 'SearchPageContextTest']

User = get_user_model()


@searchable(fields=['name'], title='name', url='demoapp_country_detail',
            owners=['sales'], tags=['catalog', 'places'])
class SalesCountries(ModelDataSource):
    model = demo.Country
    name = 'test.w21.sales_countries'
    fields = ['id', 'name', 'code']


@searchable(fields=['name'], title='name', url='demoapp_country_detail',
            owners=('hr', 'sales'), tags='people')
class SharedPeople(ModelDataSource):
    model = demo.Country
    name = 'test.w21.hr_countries'
    fields = ['id', 'name', 'code']


@searchable(fields=['name'], title='name', url='demoapp_country_detail',
            tags=['catalog'])
class EveryoneCountries(ModelDataSource):
    model = demo.Country
    name = 'test.w21.shared_countries'
    fields = ['id', 'name', 'code']


SOURCES = (SalesCountries, SharedPeople, EveryoneCountries)
NAMES = [source.name for source in SOURCES]


def by_app(request):
    """A GT_SEARCH_SOURCES hook over the owners, the way djodo narrows the
    search of an App."""
    app = request.GET.get('app') or None
    return [name for name in searchable_sources(owner=app) if name in NAMES]


def ours(found):
    return sorted(name for name in found if name in NAMES)


class SearchOwnersTest(TestCase):
    def setUp(self):
        for source in SOURCES:
            register_datasource(source)
            self.addCleanup(unregister_datasource, source.name)
        self.sources = searchable_sources(NAMES)

    def test_owners_and_tags_of_a_source(self):
        sales, hr, shared = (self.sources[name] for name in NAMES)
        self.assertEqual(source_owners(sales), ('sales',))
        self.assertEqual(source_owners(hr), ('hr', 'sales'))
        self.assertEqual(source_owners(shared), ())
        self.assertEqual(source_tags(sales), ('catalog', 'places'))
        self.assertEqual(source_tags(hr), ('people',))
        self.assertEqual(source_owners(object()), ())

    def test_who_may_search_it(self):
        sales, hr, shared = (self.sources[name] for name in NAMES)
        self.assertTrue(is_owned_by(sales, 'sales'))
        self.assertFalse(is_owned_by(sales, 'hr'))
        self.assertFalse(is_owned_by(sales, None))
        self.assertTrue(is_owned_by(hr, 'hr'))
        for owner in (None, 'sales', 'hr', 'anyone'):
            self.assertTrue(is_owned_by(shared, owner))

    def test_searchable_sources_by_owner_and_tags(self):
        self.assertEqual(ours(searchable_sources()), sorted(NAMES))
        self.assertEqual(ours(searchable_sources(owner=None)),
                         ['test.w21.shared_countries'])
        self.assertEqual(ours(searchable_sources(owner='hr')),
                         ['test.w21.hr_countries', 'test.w21.shared_countries'])
        self.assertEqual(ours(searchable_sources(owner='sales')), sorted(NAMES))
        self.assertEqual(ours(searchable_sources(tags=['catalog'])),
                         ['test.w21.sales_countries', 'test.w21.shared_countries'])
        self.assertEqual(ours(searchable_sources(tags='catalog', owner='hr')),
                         ['test.w21.shared_countries'])
        self.assertEqual(ours(searchable_sources(tags=['catalog', 'places'])),
                         ['test.w21.sales_countries'])

    def test_bad_owners(self):
        for value in ([''], [3], ['ok', None]):
            with self.subTest(value=value), self.assertRaises(ImproperlyConfigured):
                GlobalSearch(owners=value)
        self.assertEqual(GlobalSearch(owners='a').owners, ('a',))
        self.assertEqual(GlobalSearch(owners=None).owners, ())
        self.assertEqual(GlobalSearch(tags=['x', 'x']).tags, ('x',))

    @override_settings(GT_SEARCH_SOURCES='djgentelella.tests.SearchOwners_Test.by_app')
    def test_a_hook_reads_the_owners(self):
        demo.Country.objects.create(name='Costa Rica', code='cr')
        user = User.objects.create_superuser('root', 'r@example.com', 'x')
        self.client.force_login(user)

        def found(**params):
            data = self.client.get(reverse('gt-search-api'),
                                   {'q': 'costa', **params}).json()
            return sorted(group['source'] for group in data['groups'])

        self.assertEqual(found(), ['test.w21.shared_countries'])
        self.assertEqual(found(app='hr'),
                         ['test.w21.hr_countries', 'test.w21.shared_countries'])
        # An explicit source stays within what the hook allows.
        self.assertEqual(found(app='hr', sources='test.w21.sales_countries'), [])


def search_context(request):
    return {'base_template': 'gentelella/base_site.html',
            'breadcrumbs': [{'label': 'Sales', 'href': '/sales/'},
                            {'label': 'Search', 'href': ''}],
            'query': 'replaced', 'groups': 'replaced'}


def bad_search_context(request):
    return ['not', 'a', 'dict']


@override_settings(LANGUAGE_CODE='en')
class SearchPageContextTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('root', 'r@example.com', 'x')
        self.client.force_login(self.user)

    def page(self, **params):
        return self.client.get(reverse('gt-search'), {'q': 'zz', **params})

    def test_by_default_gentelellas_base(self):
        response = self.page()
        self.assertEqual(response.context['base_template'], 'gentelella/base.html')
        self.assertNotIn('gt-breadcrumb', response.content.decode())

    @override_settings(GT_SEARCH_BASE_TEMPLATE='gentelella/base_site.html')
    def test_the_base_template_setting(self):
        response = self.page()
        self.assertTemplateUsed(response, 'gentelella/base_site.html')

    @override_settings(
        GT_SEARCH_PAGE_CONTEXT='djgentelella.tests.SearchOwners_Test.search_context')
    def test_the_context_hook(self):
        response = self.page()
        content = response.content.decode()
        self.assertTemplateUsed(response, 'gentelella/base_site.html')
        self.assertIn('gt-breadcrumb', content)
        self.assertIn('href="/sales/"', content)
        # What the page itself needs is not the hook's.
        self.assertEqual(response.context['query'], 'zz')
        self.assertEqual(response.context['groups'], [])

    @override_settings(GT_SEARCH_PAGE_CONTEXT=bad_search_context)
    def test_a_hook_that_is_not_a_dict(self):
        request = RequestFactory().get('/')
        with self.assertRaises(ImproperlyConfigured):
            page_context(request)
