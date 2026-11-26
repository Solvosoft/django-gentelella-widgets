"""The menus cost a fixed number of queries, whatever the size of the tree.

They used to run several queries per item (its permissions, their content
types, its children): ~200 on every page of the demo.
"""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.core.cache import cache
from django.db import connection
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from djgentelella.forms.decorators import decore_form_instance
from djgentelella.menu import (
    item_visible, menu_tree, register_menu_widget, visible_items,
)
from djgentelella.models import MenuItem, PermissionsCategoryManagement
from djgentelella.permission_management.forms import PermCategoryManagementForm
from djgentelella.templatetags.gentelellamenu import PLACEHOLDER_URL_NAMES
from djgentelella.utils import set_settings
from djgentelella.views.select2autocomplete import (
    BaseSelect2View, model_serializer_class)

ALL_MENUS = ('{% load gentelellamenu %}{% top_menu %}{% sidebar_menu %}'
             '{% footer_sidebar_menu %}')


@register_menu_widget
class RequestWidget:
    """A menu widget, with the contract djodo's AppSwitcherMenu relies on."""

    def __init__(self, context):
        self.context = context

    def render(self):
        request = self.context.get('context')['request']
        return '<span>widget of %s</span>' % request.user.username


def build_tree(roots, children, perm):
    """``roots`` roots per menu, each with ``children`` children and a grand
    child; every other item needs ``perm``, every third has a condition."""
    count = 0
    for category in ('main', 'sidebar', 'sidebarfooter'):
        for r in range(roots):
            root = MenuItem.objects.create(
                title='%s root %d' % (category, r), url_name='/%s/%d' % (category, r),
                category=category, position=r)
            for c in range(children):
                child = MenuItem.objects.create(
                    title='%s child %d.%d' % (category, r, c), category=category,
                    url_name='/%s/%d/%d' % (category, r, c), parent=root)
                MenuItem.objects.create(
                    title='%s grandchild %d.%d' % (category, r, c),
                    category=category, parent=child,
                    url_name='/%s/%d/%d/g' % (category, r, c))
                count += 1
                if count % 2:
                    child.permission.add(perm)
                if count % 3 == 0:
                    child.condition = {'user_attr': 'is_staff'}
                    child.save()


class MenuQueriesTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.perm = Permission.objects.get(codename='view_menuitem')
        cls.user = get_user_model().objects.create_user('menu', password='x')
        cls.user.user_permissions.add(cls.perm)

    def request(self, user=None):
        request = RequestFactory().get('/')
        request.user = user or get_user_model().objects.get(pk=self.user.pk)
        return request

    def render(self, request=None):
        return Template(ALL_MENUS).render(
            Context({'request': request or self.request()}))

    def queries(self):
        with CaptureQueriesContext(connection) as ctx:
            self.render()
        return len(ctx.captured_queries)

    def test_queries_do_not_grow_with_the_tree(self):
        build_tree(roots=1, children=1, perm=self.perm)
        small = self.queries()
        MenuItem.objects.all().delete()
        build_tree(roots=5, children=6, perm=self.perm)
        self.assertEqual(MenuItem.objects.count(), 3 * (5 + 5 * 6 * 2))
        self.assertEqual(self.queries(), small)
        # The items, their permissions, the content types, the user's perms.
        self.assertLessEqual(small, 6)

    def test_menus_of_a_page_share_one_load(self):
        build_tree(roots=2, children=2, perm=self.perm)
        request = self.request()
        self.render(request)
        with CaptureQueriesContext(connection) as ctx:
            self.render(request)
        self.assertEqual(
            [q['sql'] for q in ctx.captured_queries if 'menuitem' in q['sql']], [])

    def test_permissions_and_conditions_still_apply(self):
        root = MenuItem.objects.create(title='Root', url_name='/r', category='main')
        MenuItem.objects.create(title='Open child', url_name='/r/o',
                                category='main', parent=root)
        needs_perm = MenuItem.objects.create(title='Perm child', url_name='/r/p',
                                             category='main', parent=root)
        needs_perm.permission.add(self.perm)
        MenuItem.objects.create(title='Staff child', url_name='/r/s',
                                category='main', parent=root,
                                condition={'user_attr': 'is_staff'})
        html = self.render()
        self.assertIn('Open child', html)
        self.assertIn('Perm child', html)
        self.assertNotIn('Staff child', html)

        other = get_user_model().objects.create_user('other', password='x')
        html = self.render(self.request(other))
        self.assertIn('Open child', html)
        self.assertNotIn('Perm child', html)

    def test_hidden_parent_hides_its_children(self):
        root = MenuItem.objects.create(title='Locked', url_name='/l', category='main')
        root.permission.add(Permission.objects.get(codename='add_menuitem'))
        MenuItem.objects.create(title='Inside', url_name='/l/i', category='main',
                                parent=root)
        self.assertNotIn('Inside', self.render())
        self.assertEqual(visible_items(self.request(), 'main'), [])

    def test_children_keep_the_id_order(self):
        root = MenuItem.objects.create(title='Root', url_name='/r', category='main')
        first = MenuItem.objects.create(title='First', url_name='/r/1',
                                        category='main', parent=root, position=9)
        second = MenuItem.objects.create(title='Second', url_name='/r/2',
                                         category='main', parent=root, position=1)
        self.assertEqual(menu_tree(self.request()).children(root), [first, second])

    def test_widget_gets_the_request(self):
        MenuItem.objects.create(
            title='Switcher', is_widget=True, category='main',
            url_name='djgentelella.tests.MenuQueries_Test.RequestWidget')
        self.assertIn('widget of menu', self.render())

    def test_visible_items(self):
        root = MenuItem.objects.create(title='Root', url_name='/r', category='main',
                                       position=1)
        child = MenuItem.objects.create(title='Child', url_name='/r/c',
                                        category='main', parent=root)
        hidden = MenuItem.objects.create(title='Hidden', url_name='/r/h',
                                         category='main', parent=root)
        hidden.permission.add(Permission.objects.get(codename='add_menuitem'))
        side = MenuItem.objects.create(title='Side', url_name='/s',
                                       category='sidebar')
        request = self.request()
        self.assertEqual(visible_items(request, 'main'), [(root, 0), (child, 1)])
        self.assertEqual(visible_items(request, 'sidebar'), [(side, 0)])
        self.assertTrue(item_visible(child, request))
        self.assertFalse(item_visible(hidden, request))

    def test_anonymous_user(self):
        MenuItem.objects.create(title='Public', url_name='/p', category='main')
        locked = MenuItem.objects.create(title='Locked', url_name='/l',
                                         category='main')
        locked.permission.add(self.perm)
        request = RequestFactory().get('/')
        request.user = AnonymousUser()
        html = self.render(request)
        self.assertIn('Public', html)
        self.assertNotIn('Locked', html)

    def test_placeholder_url_names_still_importable_from_the_tags(self):
        self.assertEqual(PLACEHOLDER_URL_NAMES, frozenset(('', '/', '#')))


class PermissionFieldQueriesTest(TestCase):
    """``str(permission)`` reads its content type: one query per option."""

    def rendered_queries(self, form):
        with CaptureQueriesContext(connection) as ctx:
            str(form['permissions'])
        return len(ctx.captured_queries)

    def test_permission_management_form(self):
        self.assertLessEqual(self.rendered_queries(PermCategoryManagementForm()), 2)

    def test_decore_form_instance(self):
        class GroupForm(forms.ModelForm):
            class Meta:
                model = Group
                fields = ['name', 'permissions']

        form = decore_form_instance(GroupForm())
        self.assertGreater(Permission.objects.count(), 50)
        self.assertLessEqual(self.rendered_queries(form), 2)


class GroupLookup(BaseSelect2View):
    model = Group
    fields = ['name']


class Select2SerializerTest(TestCase):
    """The serializer class is built once per view, not once per request."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('root', password='x')
        Group.objects.create(name='Alpha')
        Group.objects.create(name='Beta')

    def test_same_class_and_the_right_view(self):
        first = model_serializer_class(GroupLookup(), ['id', 'text'])
        self.assertIs(model_serializer_class(GroupLookup(), ['id', 'text']), first)
        self.client.force_login(self.admin)
        for _ in range(2):
            response = self.client.get('/gtapis/groupbase/', {'selected': ''})
            self.assertEqual(response.status_code, 200)
            self.assertEqual([r['text'] for r in response.json()['results']],
                             ['Alpha', 'Beta'])


class SidebarTitleTest(TestCase):
    """``sidebar_title`` in the context wins over the configured title."""

    def render(self, **context):
        request = RequestFactory().get('/')
        request.user = AnonymousUser()
        return render_to_string('gentelella/app/sidebar.html',
                                {'request': request, **context})

    def test_configured_title_by_default(self):
        set_settings('sidebar_title', 'Configured')
        self.assertIn('<span>Configured</span>', self.render())

    def test_context_title_wins(self):
        set_settings('sidebar_title', 'Configured')
        html = self.render(sidebar_title='Aplicaciones <b>')
        self.assertIn('<span>Aplicaciones &lt;b&gt;</span>', html)
        self.assertNotIn('Configured', html)


@override_settings(LANGUAGE_CODE='en')
class PageQueriesTest(TestCase):
    """What the layout of every page costs once its caches are warm: the menu
    (two queries), the session and the user. Settings nobody set, the PWA tags
    and the home template used to add a query each, or a write."""

    def setUp(self):
        cache.clear()
        user = get_user_model().objects.create_superuser('pages', 'p@x.org', 'pw')
        self.client.force_login(user)

    def test_a_warm_page_takes_four_queries(self):
        url = reverse('home')
        self.client.get(url)
        with self.assertNumQueries(4):
            self.assertEqual(self.client.get(url).status_code, 200)

    @override_settings(GT_PWA_MANIFEST=True, GT_PWA_SERVICE_WORKER=True)
    def test_the_pwa_tags_add_none(self):
        self.test_a_warm_page_takes_four_queries()

    def test_the_home_page_writes_nothing(self):
        self.client.get(reverse('home'))
        self.assertFalse(PermissionsCategoryManagement.objects.exists())
