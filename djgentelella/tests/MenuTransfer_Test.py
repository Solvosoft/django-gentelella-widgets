"""The natural key of ``MenuItem`` and the menu as data:
``djgentelella.menu.export_tree`` / ``validate_tree`` / ``import_tree`` (W20).
"""
from django.contrib.auth.models import Permission
from django.contrib.sites.models import Site
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from djgentelella.menu import export_tree, import_tree, menu_tree, validate_tree
from djgentelella.models import MenuItem


def node(title, url_name='/x', **fields):
    data = {'title': title, 'url_name': url_name}
    data.update(fields)
    return data


class MenuItemKeyTests(TestCase):
    def setUp(self):
        self.site = Site.objects.create(domain='ventas.example.com', name='Ventas')

    def test_a_key_is_unique_in_its_scope(self):
        MenuItem.objects.create(title='A', url_name='/a', key='home')
        MenuItem.objects.create(title='A', url_name='/a', key='home', site=self.site)
        with self.assertRaises(IntegrityError), transaction.atomic():
            MenuItem.objects.create(title='B', url_name='/b', key='home')
        with self.assertRaises(IntegrityError), transaction.atomic():
            MenuItem.objects.create(title='B', url_name='/b', key='home',
                                    site=self.site)

    def test_without_a_key_nothing_is_unique(self):
        for _ in range(2):
            MenuItem.objects.create(title='A', url_name='/a')
            MenuItem.objects.create(title='A', url_name='/a', key='')
        self.assertEqual(MenuItem.objects.filter(key__isnull=True).count(), 4)

    def test_get_by_natural_key(self):
        own = MenuItem.objects.create(title='A', url_name='/a', key='home',
                                      site=self.site)
        global_ = MenuItem.objects.create(title='A', url_name='/a', key='home')
        self.assertEqual(MenuItem.objects.get_by_natural_key(
            'home', 'ventas.example.com'), own)
        self.assertEqual(MenuItem.objects.get_by_natural_key('home'), global_)
        with self.assertRaises(MenuItem.DoesNotExist):
            MenuItem.objects.get_by_natural_key(None)

    def test_no_natural_key_for_the_serializers(self):
        # Items without a key would break dumpdata --natural-foreign.
        self.assertFalse(hasattr(MenuItem, 'natural_key'))


@override_settings(LANGUAGE_CODE='en')
class MenuTransferTests(TestCase):
    def setUp(self):
        self.site = Site.objects.create(domain='ventas.example.com', name='Ventas')
        self.other = Site.objects.create(domain='other.example.com', name='Other')
        self.perm = Permission.objects.get(codename='add_menuitem')
        self.global_root = MenuItem.objects.create(
            title='Apps', url_name='#', category='main', key='apps')
        self.root = MenuItem.objects.create(
            title='Sales', url_name='/sales', site=self.site, position=2,
            key='sales', icon='fa fa-money', condition={'perm': 'auth.view_user'})
        self.root.permission.add(self.perm)
        self.child = MenuItem.objects.create(
            title='Orders', url_name='orders', is_reversed=True, site=self.site,
            parent=self.root)
        self.under_global = MenuItem.objects.create(
            title='Ventas app', url_name='/v', site=self.site,
            parent=self.global_root, position=1)
        MenuItem.objects.create(title='Elsewhere', url_name='/e', site=self.other)

    def test_export(self):
        data = export_tree(self.site)
        self.assertEqual([item['title'] for item in data], ['Ventas app', 'Sales'])
        sales = data[1]
        self.assertEqual(sales['key'], 'sales')
        self.assertEqual(sales['permissions'], ['djgentelella.add_menuitem'])
        self.assertEqual(sales['condition'], {'perm': 'auth.view_user'})
        self.assertEqual(sales['icon'], 'fa fa-money')
        self.assertEqual(sales['children'][0]['title'], 'Orders')
        self.assertTrue(sales['children'][0]['is_reversed'])
        self.assertNotIn('global_parent', sales)
        self.assertEqual(data[0]['global_parent'], {
            'key': 'apps', 'title': 'Apps', 'url_name': '#', 'category': 'main'})
        self.assertNotIn('id', sales)
        self.assertNotIn('pk', sales)

    def test_export_the_global_menu(self):
        self.assertEqual([item['title'] for item in export_tree()], ['Apps'])

    def test_a_round_trip_into_another_site(self):
        data = export_tree(self.site)
        roots, errors = import_tree(data, self.other)
        self.assertEqual(errors, [])
        self.assertEqual(len(roots), 2)
        self.assertEqual(export_tree(self.other), data)
        self.assertFalse(MenuItem.objects.filter(site=self.other,
                                                 title='Elsewhere').exists())
        # The source is untouched.
        self.assertEqual(MenuItem.objects.filter(site=self.site).count(), 3)
        copy = MenuItem.objects.get(site=self.other, key='sales')
        self.assertEqual(copy.children.get().title, 'Orders')
        self.assertEqual(MenuItem.objects.get(site=self.other,
                                              title='Ventas app').parent,
                         self.global_root)

    def test_importing_again_updates_keyed_items_in_place(self):
        data = export_tree(self.site)
        data[1]['title'] = 'Sales and more'
        data[1]['children'].append(node('Invoices', '/invoices', key='invoices'))
        roots, errors = import_tree(data, self.site)
        self.assertEqual(errors, [])
        sales = MenuItem.objects.get(site=self.site, key='sales')
        self.assertEqual(sales.pk, self.root.pk)
        self.assertEqual(sales.title, 'Sales and more')
        self.assertEqual(sorted(sales.children.values_list('title', flat=True)),
                         ['Invoices', 'Orders'])
        # The items without a key were created again.
        self.assertFalse(MenuItem.objects.filter(pk=self.child.pk).exists())
        self.assertEqual(MenuItem.objects.filter(site=self.site).count(), 4)

    def test_without_replace_the_other_items_stay(self):
        roots, errors = import_tree([node('Reports', '/reports', key='reports')],
                                    self.site, replace=False)
        self.assertEqual(errors, [])
        self.assertEqual(MenuItem.objects.filter(site=self.site).count(), 4)
        roots, errors = import_tree([node('Reports!', '/reports', key='reports')],
                                    self.site, replace=False)
        self.assertEqual(MenuItem.objects.get(site=self.site, key='reports').title,
                         'Reports!')
        self.assertEqual(MenuItem.objects.filter(site=self.site).count(), 4)

    def test_replace_leaves_the_global_items(self):
        roots, errors = import_tree([], self.site)
        self.assertEqual(errors, [])
        self.assertFalse(MenuItem.objects.filter(site=self.site).exists())
        self.assertTrue(MenuItem.objects.filter(pk=self.global_root.pk).exists())

    def assertErrors(self, data, *paths, site='site'):
        before = list(MenuItem.objects.order_by('pk').values())
        roots, errors = import_tree(data, getattr(self, site) if site else None)
        self.assertIsNone(roots)
        self.assertEqual([error.path for error in errors], list(paths), errors)
        self.assertEqual(list(MenuItem.objects.order_by('pk').values()), before)
        return errors

    def test_nothing_is_written_with_errors(self):
        self.assertErrors([node('Ok', key='ok'), node('', key='Bad Key')],
                          '$[1].title', '$[1].key')
        self.assertErrors({'title': 'x'}, '$')
        self.assertErrors([node('A', key='a'), node('B', key='a')], '$[1].key')
        self.assertErrors([node('A', position='1')], '$[0].position')
        self.assertErrors([node('A', is_widget=1)], '$[0].is_widget')
        self.assertErrors([node('A', id=3)], '$[0].id')
        self.assertErrors([{'title': 'A'}], '$[0].url_name')
        self.assertErrors([node('x' * 501)], '$[0].title')
        self.assertErrors([node('A', children={})], '$[0].children')

    def test_permissions_conditions_and_widgets_are_checked(self):
        self.assertErrors([node('A', permissions=['auth.nothing'])],
                          '$[0].permissions')
        self.assertErrors([node('A', condition={'auth': 'nobody.knows'})],
                          '$[0].condition.auth')
        with self.assertLogs('djgentelella.menu', 'WARNING'):
            self.assertErrors([node('A', url_name='os.system', is_widget=True)],
                              '$[0].url_name')

    def test_the_global_parent(self):
        self.assertErrors([node('A', global_parent={'key': 'nothing'})],
                          '$[0].global_parent')
        self.assertErrors([node('A', children=[
            node('B', global_parent={'key': 'apps'})])],
            '$[0].children[0].global_parent')
        # The global menu hangs from nothing.
        self.assertErrors([node('A', global_parent={'key': 'apps'})],
                          '$[0].global_parent', site=None)
        roots, errors = import_tree([node('A', global_parent={
            'key': None, 'title': 'Apps', 'url_name': '#', 'category': 'main'})],
            self.other)
        self.assertEqual(roots[0].parent, self.global_root)

    def test_too_deep(self):
        data = current = node('0')
        for level in range(1, 11):
            child = node(str(level))
            current['children'] = [child]
            current = child
        errors = validate_tree([data])
        self.assertEqual(len(errors), 1)
        self.assertIn('deeper than 10', errors[0].message)

    def test_defaults_of_missing_fields(self):
        roots, errors = import_tree([node('Plain', '/plain')], self.other)
        item = roots[0]
        self.assertEqual((item.category, item.is_reversed, item.is_widget,
                          item.position, item.key, item.condition, item.site),
                         ('main', False, False, 0, None, None, self.other))

    def test_validate_for_a_site_not_created_yet(self):
        new = Site(domain='nuevo.example.com', name='Nuevo')
        data = [node('A', global_parent={'key': 'apps'})]
        self.assertEqual(validate_tree(data, new), [])
        self.assertIsNone(new.pk)

    def test_export_warns_of_a_parent_of_another_site(self):
        foreign = MenuItem.objects.create(title='Foreign', url_name='/f',
                                          site=self.other)
        MenuItem.objects.create(title='Stray', url_name='/s', site=self.site,
                                parent=foreign, position=3)
        plain = export_tree(self.site)
        warnings = []
        data = export_tree(self.site, warnings=warnings)
        self.assertEqual(data, plain)
        self.assertEqual([item['title'] for item in data],
                         ['Ventas app', 'Sales', 'Stray'])
        self.assertEqual([(str(error.path), error.message) for error in warnings], [
            ('$[2]', '"Stray" hangs from "Foreign" of another scope '
                     '(other.example.com) and is exported as a root')])

    def test_export_of_the_global_menu_warns_of_a_site_parent(self):
        MenuItem.objects.create(title='Global under site', url_name='/g',
                                parent=self.root)
        warnings = []
        data = export_tree(warnings=warnings)
        self.assertEqual([item['title'] for item in data],
                         ['Apps', 'Global under site'])
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].path, '$[1]')
        self.assertIn('ventas.example.com', warnings[0].message)

    def test_no_warnings_for_a_clean_menu(self):
        warnings = []
        export_tree(self.site, warnings=warnings)
        self.assertEqual(warnings, [])


class MenuTransferOrderTests(TestCase):
    def test_children_are_exported_in_the_order_the_menus_draw_them(self):
        # Children are drawn by id, whatever their position (menus.rst): an
        # exported and imported menu must draw them in the same order.
        site = Site.objects.create(domain='orden.example.com', name='Orden')
        root = MenuItem.objects.create(title='Root', url_name='#', site=site,
                                       position=0)
        MenuItem.objects.create(title='First', url_name='/1', parent=root,
                                site=site, position=9)
        MenuItem.objects.create(title='Second', url_name='/2', parent=root,
                                site=site, position=0)
        drawn = [item.title for item in menu_tree(site=site).children(root)]
        self.assertEqual(drawn, ['First', 'Second'])
        data = export_tree(site)
        self.assertEqual([child['title'] for child in data[0]['children']], drawn)
        other = Site.objects.create(domain='copia.example.com', name='Copia')
        roots, errors = import_tree(data, other)
        self.assertEqual(errors, [])
        self.assertEqual([item.title for item in
                          menu_tree(site=other).children(roots[0])], drawn)
