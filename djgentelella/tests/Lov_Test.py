import json

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.test import Client, TestCase
from django.urls import reverse

from djgentelella.fields.lov import LOVChoiceField, LOVMultipleChoiceField
from djgentelella.forms.forms import GTForm
from djgentelella.lov import get_lov, get_lovs, register_lov, unregister_lov
from djgentelella.widgets.lov import LOVSelect, LOVSelectMultiple

PROVINCES = {'cr': [('sj', 'San José'), ('al', 'Alajuela')],
             'pa': [('ch', 'Chiriquí')]}
CANTONS = {'sj': [('sj1', 'Escazú'), ('sj2', 'Desamparados')],
           'al': [('al1', 'San Ramón')]}


@register_lov('test_countries', login_required=False)
def countries(request, q=''):
    return [(code, name) for code, name in [('cr', 'Costa Rica'), ('pa', 'Panamá')]
            if q.lower() in name.lower()]


@register_lov('test_provinces', depends_on=['country'])
def provinces(request, country=None, q=''):
    return PROVINCES.get(country, [])


@register_lov('test_cantons', depends_on=['province'])
def cantons(request, province=None, q=''):
    return CANTONS.get(province, [])


@register_lov('test_groups', perms=['auth.view_group'], page_size=2)
def groups(request, q=''):
    return Group.objects.filter(name__icontains=q).order_by('name')


@register_lov('test_permissions', depends_on=['ct'], login_required=False)
def permissions(request, ct=None, q=''):
    # The documented pattern: the parent straight into an integer foreign key.
    return Permission.objects.filter(content_type_id=ct, name__icontains=q)


@register_lov('test_int_parent', depends_on=['level'], login_required=False)
def int_parent(request, level=None, q=''):
    # A list LOV that converts its parent by hand.
    return [(str(n), 'Item %s' % n) for n in range(int(level or 0))]


@register_lov('test_group_names', login_required=False)
def group_names(request, q=''):
    # The option value is the name, not the pk.
    return Group.objects.filter(name__icontains=q).order_by('name').values_list(
        'name', 'name')


@register_lov('test_group_dicts', login_required=False)
def group_dicts(request, q=''):
    return Group.objects.order_by('name').values('name', 'pk')


class PermissionForm(GTForm):
    ct = forms.CharField()
    permission = LOVChoiceField('test_permissions', coerce=int)


class AddressForm(GTForm):
    country = LOVChoiceField('test_countries')
    province = LOVChoiceField('test_provinces', required=False)
    canton = LOVChoiceField('test_cantons', required=False)


class RenamedParentForm(GTForm):
    pais = LOVChoiceField('test_countries')
    provincia = LOVChoiceField('test_provinces', parents={'country': 'pais'})


class GroupsForm(GTForm):
    group = LOVChoiceField('test_groups', coerce=int)
    groups = LOVMultipleChoiceField('test_groups', required=False)


class LOVRegistryTest(TestCase):
    def test_owner_lists_the_lovs_of_who_registered_them(self):
        def values(request, q=''):
            return []

        register_lov('owned.a', owner='djodo.app.ventas')(values)
        register_lov('owned.b', owner='djodo.app.ventas')(values)
        register_lov('owned.c', owner='djodo.app.compras')(values)
        self.addCleanup(lambda: [unregister_lov(name)
                                 for name in ('owned.a', 'owned.b', 'owned.c')])
        self.assertEqual(sorted(get_lovs(owner='djodo.app.ventas')),
                         ['owned.a', 'owned.b'])
        self.assertEqual(get_lov('owned.c').owner, 'djodo.app.compras')
        # Without owner, every LOV, owned or not; a LOV of nobody has ''.
        self.assertTrue({'owned.a', 'test_countries'} <= set(get_lovs()))
        self.assertEqual(get_lov('test_countries').owner, '')
        self.assertEqual(get_lovs(owner='nobody'), {})

    def test_registered_and_autodiscovered(self):
        self.assertEqual(get_lov('test_provinces').depends_on, ['country'])
        # demoapp/gtlovs.py, found by the autodiscovery.
        self.assertIn('demo_cantons', get_lovs())
        with self.assertRaises(LookupError):
            get_lov('nope')

    def test_bad_registrations(self):
        with self.assertRaises(ImproperlyConfigured):
            register_lov('a/b')
        with self.assertRaises(ImproperlyConfigured):
            register_lov('x', depends_on='country')(lambda request, q='': [])
        unregister_lov('x')

    def test_find_in_lists_and_querysets(self):
        lov = get_lov('test_provinces')
        self.assertEqual(lov.label('sj', {'country': 'cr'}), 'San José')
        self.assertIsNone(lov.label('sj', {'country': 'pa'}))
        self.assertFalse(lov.contains('', {'country': 'cr'}))
        group = Group.objects.create(name='Admins')
        self.assertTrue(get_lov('test_groups').contains(group.pk))
        self.assertFalse(get_lov('test_groups').contains('not-a-pk'))

    def test_find_in_a_values_list_compares_the_first_column(self):
        admins = Group.objects.create(name='Admins')
        Group.objects.create(name=str(admins.pk))  # a name equal to a pk
        lov = get_lov('test_group_names')
        options, _more = lov.page(None)
        self.assertIn(('Admins', 'Admins'), options)
        # What page() offers is what find() accepts, and nothing else.
        for value, label in options:
            self.assertEqual(lov.find(value), (value, label))
        self.assertEqual(lov.label('Admins'), 'Admins')
        self.assertEqual(lov.find(str(admins.pk)), (str(admins.pk), str(admins.pk)))
        self.assertIsNone(lov.find('Nobody'))
        Group.objects.filter(name=str(admins.pk)).delete()
        self.assertIsNone(lov.find(admins.pk))  # a pk is not a value here

    def test_find_in_values(self):
        admins = Group.objects.create(name='Admins')
        lov = get_lov('test_group_dicts')
        self.assertIn(('Admins', str(admins.pk)), lov.page(None)[0])
        self.assertEqual(lov.find('Admins'), ('Admins', str(admins.pk)))
        self.assertIsNone(lov.find(admins.pk))


class LOVEndpointTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('lov', password='x')
        self.client.force_login(self.user)

    def get(self, name, client=None, **params):
        return (client or self.client).get(reverse('gt-lov', args=[name]), params)

    def test_select2_format_with_parents(self):
        response = self.get('test_provinces', country='cr')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'results': [{'id': 'sj', 'text': 'San José'},
                        {'id': 'al', 'text': 'Alajuela'}],
            'pagination': {'more': False}})
        self.assertEqual(self.get('test_provinces').json()['results'], [])

    def test_search(self):
        response = self.get('test_countries', q='pan')
        self.assertEqual(response.json()['results'], [{'id': 'pa', 'text': 'Panamá'}])

    def test_unknown_is_404(self):
        self.assertEqual(self.get('missing').status_code, 404)

    def test_login_required_by_default(self):
        anonymous = Client()
        self.assertEqual(self.get('test_provinces', anonymous).status_code, 403)
        self.assertEqual(self.get('test_countries', anonymous).status_code, 200)

    def test_perms(self):
        for name in ('a', 'b', 'c'):
            Group.objects.create(name=name)
        self.assertEqual(self.get('test_groups').status_code, 403)
        self.assertEqual(self.get('test_groups', Client()).status_code, 403)
        self.user.user_permissions.add(Permission.objects.get(codename='view_group'))
        self.user = get_user_model().objects.get(pk=self.user.pk)
        self.client.force_login(self.user)
        first = self.get('test_groups').json()
        self.assertEqual([r['text'] for r in first['results']], ['a', 'b'])
        self.assertTrue(first['pagination']['more'])
        second = self.get('test_groups', page=2).json()
        self.assertEqual([r['text'] for r in second['results']], ['c'])
        self.assertFalse(second['pagination']['more'])

    def test_bad_page_is_400(self):
        self.assertEqual(self.get('test_countries', page='x').status_code, 400)
        self.assertEqual(self.get('test_countries', page='0').status_code, 400)
        for big in ('10001', '9' * 19, '9' * 40):
            self.assertEqual(self.get('test_countries', page=big).status_code, 400)

    def test_invalid_parent_is_an_empty_list_not_a_500(self):
        ct = ContentType.objects.get_for_model(Group)
        response = self.get('test_permissions', ct=ct.pk)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['results'])
        for bad in ('abc', '1.5', '9' * 40):
            response = self.get('test_permissions', ct=bad)
            self.assertEqual(response.status_code, 200, bad)
            self.assertEqual(response.json(),
                             {'results': [], 'pagination': {'more': False}})
        response = self.get('test_int_parent', level='abc')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'], [])
        self.assertEqual(len(self.get('test_int_parent', level='2')
                             .json()['results']), 2)

    def test_find_with_an_invalid_parent(self):
        lov = get_lov('test_permissions')
        self.assertIsNone(lov.find('1', {'ct': 'abc'}))
        self.assertFalse(lov.contains('1', {'ct': 'abc'}))
        self.assertIsNone(get_lov('test_int_parent').label('1', {'level': 'x'}))

    def test_only_get(self):
        response = self.client.post(reverse('gt-lov', args=['test_countries']))
        self.assertEqual(response.status_code, 405)


class LOVFieldTest(TestCase):
    def test_accepts_a_value_of_its_parent(self):
        form = AddressForm(data={'country': 'cr', 'province': 'sj', 'canton': 'sj2'})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data,
                         {'country': 'cr', 'province': 'sj', 'canton': 'sj2'})

    def test_rejects_a_value_of_another_parent(self):
        form = AddressForm(data={'country': 'pa', 'province': 'sj', 'canton': 'al1'})
        self.assertFalse(form.is_valid())
        self.assertIn('province', form.errors)
        self.assertIn('canton', form.errors)
        self.assertNotIn('country', form.errors)

    def test_rejects_a_value_not_in_the_lov(self):
        form = AddressForm(data={'country': 'xx'})
        self.assertFalse(form.is_valid())
        self.assertIn('country', form.errors)

    def test_a_tampered_parent_is_invalid_choice_not_a_500(self):
        ct = ContentType.objects.get_for_model(Group)
        permission = Permission.objects.filter(content_type=ct).first()
        form = PermissionForm({'ct': 'abc', 'permission': str(permission.pk)})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.as_data()['permission'][0].code,
                         'invalid_choice')
        # Rendering the bound form asks the LOV for the selected label.
        html = str(form)
        self.assertIn('value="%s"' % permission.pk, html)
        form = PermissionForm({'ct': str(ct.pk), 'permission': str(permission.pk)})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['permission'], permission.pk)

    def test_parents_with_a_prefix_and_renamed(self):
        form = AddressForm(prefix='a', data={'a-country': 'cr', 'a-province': 'al'})
        self.assertTrue(form.is_valid(), form.errors)
        form = RenamedParentForm(data={'pais': 'pa', 'provincia': 'ch'})
        self.assertTrue(form.is_valid(), form.errors)
        form = RenamedParentForm(data={'pais': 'cr', 'provincia': 'ch'})
        self.assertFalse(form.is_valid())

    def test_queryset_lov_and_multiple(self):
        a = Group.objects.create(name='a')
        b = Group.objects.create(name='b')
        form = GroupsForm(data={'group': str(a.pk), 'groups': [a.pk, b.pk]})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['group'], a.pk)
        self.assertEqual(form.cleaned_data['groups'], [str(a.pk), str(b.pk)])
        form = GroupsForm(data={'group': '999', 'groups': [a.pk, 999]})
        self.assertFalse(form.is_valid())
        self.assertEqual(set(form.errors), {'group', 'groups'})

    def test_widget_renders_the_selected_label_and_its_wiring(self):
        form = AddressForm(initial={'country': 'cr', 'province': 'al'}, prefix='x')
        html = str(form['province'])
        self.assertIn('data-widget="LOVSelect"', html)
        self.assertIn('data-url="%s"' % reverse('gt-lov', args=['test_provinces']),
                      html)
        self.assertIn('data-lov-prefix="x"', html)
        self.assertIn('data-lov-depends="%s"' % json.dumps({'country': 'country'})
                      .replace('"', '&quot;'), html)
        self.assertInHTML('<option value="al" selected>Alajuela</option>', html)
        self.assertInHTML('<option value=""></option>', html)
        # Only the selected value: the rest comes from the endpoint.
        self.assertNotIn('San José', html)

    def test_label_is_escaped(self):
        @register_lov('test_xss', login_required=False)
        def xss(request, q=''):
            return [('1', '<img src=x onerror=alert(1)>')]

        class XForm(forms.Form):
            x = LOVChoiceField('test_xss')

        html = str(XForm(initial={'x': '1'})['x'])
        self.assertNotIn('<img', html)
        self.assertIn('&lt;img', html)
        unregister_lov('test_xss')

    def test_widgets_standalone(self):
        html = LOVSelectMultiple('test_countries').render('c', ['cr', 'pa'])
        self.assertIn('data-widget="LOVSelectMultiple"', html)
        self.assertIn('multiple', html)
        self.assertIn('>Costa Rica<', html)
        self.assertNotIn('data-lov-prefix', LOVSelect('test_countries').render('c', ''))
        with self.assertRaises(TypeError):
            LOVSelect('')
