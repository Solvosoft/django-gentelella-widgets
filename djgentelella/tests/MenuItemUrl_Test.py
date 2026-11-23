"""The link of a menu item: djgentelella.menu.item_url, the function the menu
tags use and the one other views of the menu tree (breadcrumbs) can import."""

from django.contrib.auth.models import User
from django.template import Context, RequestContext, Template
from django.test import RequestFactory, TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from djgentelella import menu
from djgentelella.models import MenuItem
from djgentelella.templatetags._utils import get_link


#: A URLconf without djgentelella.designs: no ``gt-design-page`` route.
urlpatterns = []


def item(**fields):
    fields.setdefault('title', 'Item')
    return MenuItem(**fields)


class ItemUrlTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('menu', password='pw')
        self.request = RequestFactory().get('/')
        self.request.user = self.user

    def test_a_plain_url_is_kept(self):
        self.assertEqual(menu.item_url(item(url_name='/reports/')), '/reports/')
        self.assertEqual(menu.item_url(item(url_name='https://example.com/x')),
                         'https://example.com/x')
        self.assertEqual(menu.item_url(item(url_name='#')), '#')

    def test_a_widget_has_no_link(self):
        self.assertEqual(menu.item_url(item(url_name='a.Widget', is_widget=True)),
                         '')

    def test_a_reversed_url_name(self):
        reversed_item = item(url_name='flow_inbox', is_reversed=True,
                             reversed_args='"sales.order"')
        self.assertEqual(menu.item_url(reversed_item),
                         reverse('flow_inbox', args=['sales.order']))

    def test_arguments_from_the_template_context(self):
        context = RequestContext(self.request, {})
        by_args = item(url_name='gt-design-page', is_reversed=True,
                       reversed_args='request.user.pk')
        self.assertEqual(menu.item_url(by_args, context),
                         reverse('gt-design-page', args=[str(self.user.pk)]))
        by_kwargs = item(url_name='gt-design-endpoint', is_reversed=True,
                         reversed_kwargs='page_id: "7", node_id:table, rest:""')
        self.assertEqual(menu.item_url(by_kwargs, context), reverse(
            'gt-design-endpoint', kwargs={'page_id': 7, 'node_id': 'table',
                                          'rest': ''}))
        # A dict (or a template context) is read key by key too.
        self.assertEqual(menu.item_url(by_args, {'request': self.request}),
                         reverse('gt-design-page', args=[str(self.user.pk)]))
        self.assertEqual(menu.item_url(by_args, Context({'request': self.request})),
                         reverse('gt-design-page', args=[str(self.user.pk)]))

    def test_a_design_page(self):
        self.assertEqual(menu.item_url(item(url_name='page:sales/clients/')),
                         reverse('gt-design-page', args=['sales/clients']))
        self.assertEqual(menu.item_url(item(url_name='page:')), '')

    def test_a_broken_reverse(self):
        broken = item(url_name='no-such-view', is_reversed=True)
        with self.assertRaises(NoReverseMatch):
            menu.item_url(broken)
        self.assertEqual(menu.item_url(broken, fail_silently=True), '')
        malformed = item(url_name='flow_inbox', is_reversed=True,
                         reversed_kwargs='a:b:c')
        with self.assertRaises(ValueError):
            menu.item_url(malformed)
        self.assertEqual(menu.item_url(malformed, fail_silently=True), '')

    def test_context_values(self):
        context = {'request': self.request}
        self.assertEqual(menu.context_value(' "a.b" ', context), 'a.b')
        self.assertEqual(menu.context_value('plain', context), 'plain')
        self.assertEqual(menu.context_value('request.user.username', context), 'menu')
        self.assertIsNone(menu.context_value('request.nothing.here', context))

    def test_the_menu_tags_use_it(self):
        self.assertEqual(get_link(item(url_name='page:clients'),
                                  {'context': Context({})}),
                         reverse('gt-design-page', args=['clients']))
        MenuItem.objects.create(title='Section', url_name='#', category='sidebar')
        section = MenuItem.objects.get(title='Section')
        MenuItem.objects.create(title='Clients', url_name='page:clients',
                                category='sidebar', parent=section)
        html = Template('{% load gentelellamenu %}{% sidebar_menu %}').render(
            RequestContext(self.request, {}))
        self.assertIn('href="%s"' % reverse('gt-design-page', args=['clients']), html)

    @override_settings(ROOT_URLCONF=__name__)
    def test_a_design_page_without_the_designs_app(self):
        # The route is missing: the text is the link and the menu still draws.
        self.assertEqual(menu.item_url(item(url_name='page:clients')),
                         'page:clients')
        section = MenuItem.objects.create(title='Section', url_name='#',
                                          category='sidebar')
        MenuItem.objects.create(title='Clients', url_name='page:clients',
                                category='sidebar', parent=section)
        html = Template('{% load gentelellamenu %}{% sidebar_menu %}').render(
            RequestContext(self.request, {}))
        self.assertIn('href="page:clients"', html)
