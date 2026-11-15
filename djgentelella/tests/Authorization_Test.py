"""Authorizations, conditions and feature flags."""

from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.http import HttpResponse
from django.template import Context, Template, TemplateSyntaxError
from django.test import RequestFactory, TestCase, override_settings
from django.views import View
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from demoapp.models import Country
from djgentelella import authorization as auth_module
from djgentelella.admin import MenuItemForm
from djgentelella.authorization import (
    ConditionPermission,
    ConditionRequest,
    ConditionRequiredMixin,
    authorization,
    check_authorization,
    condition_required,
    evaluate_condition,
    flag_enabled,
    flag_names,
    flag_value,
    get_authorizations,
    set_flag,
    site_groups,
    validate_condition,
)
from djgentelella.designs import engine, publishing
from djgentelella.designs.registry import register
from djgentelella.flows import Flow, Transition, publish_definition
from djgentelella.models import GentelellaSettings, MenuItem
from djgentelella.tests.Designs_Test import DesignState, design, node
from djgentelella.tests.designs_fixtures.components import EchoComponent
from djgentelella.utils import set_settings

HOSTS = ['testserver', 'a.test', 'b.test']
CALLS = []


@authorization('tests.c6.staff')
def is_staff_rule(request, obj=None):
    CALLS.append(('staff', obj))
    return request.user.is_staff


@authorization('tests.c6.owner')
def is_owner_rule(request, obj=None):
    CALLS.append(('owner', obj))
    return obj is None or obj.name == request.user.username


@authorization('tests.c6.fresh', cache=False)
def fresh_rule(request, obj=None):
    CALLS.append(('fresh', obj))
    return True


@authorization('tests.c6.broken')
def broken_rule(request, obj=None):
    raise RuntimeError('the rule itself fails')


def only_finance(user, site):
    """A GT_SITE_GROUPS_RESOLVER: on a.test only the Finanzas group counts."""
    groups = user.groups.all() if user.is_authenticated else Group.objects.none()
    if site is not None and site.domain == 'a.test':
        return groups.filter(name='Finanzas')
    return groups


def make_user(name, *codenames, staff=False, superuser=False, groups=()):
    # No password: hashing one costs a second, and force_login needs none.
    user = get_user_model().objects.create_user(name, is_staff=staff,
                                                is_superuser=superuser)
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
    for group in groups:
        user.groups.add(group)
    # has_perm caches what it read: start again from the database.
    return get_user_model().objects.get(pk=user.pk)


def make_request(user=None, host='testserver', path='/'):
    request = RequestFactory().get(path, HTTP_HOST=host)
    request.user = user if user is not None else AnonymousUser()
    return request


class ConditionCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site_a = Site.objects.create(domain='a.test', name='A')
        cls.site_b = Site.objects.create(domain='b.test', name='B')
        cls.finance = Group.objects.create(name='Finanzas')
        cls.sales = Group.objects.create(name='Ventas')

    def setUp(self):
        cache.clear()
        Site.objects.clear_cache()
        CALLS.clear()


@override_settings(ALLOWED_HOSTS=HOSTS)
class EvaluateConditionTests(ConditionCase):
    def setUp(self):
        super().setUp()
        self.viewer = make_user('viewer', 'view_country')
        self.staff = make_user('boss', staff=True, groups=[self.finance])
        self.root = make_user('root', superuser=True)

    def holds(self, cond, user=None, host='testserver', obj=None):
        return evaluate_condition(cond, make_request(user, host), obj)

    def test_none_holds(self):
        self.assertTrue(evaluate_condition(None, None))
        self.assertTrue(self.holds(None))

    def test_perm(self):
        cond = {'perm': 'demoapp.view_country'}
        self.assertTrue(self.holds(cond, self.viewer))
        self.assertFalse(self.holds(cond, self.staff))
        self.assertFalse(self.holds(cond))  # anonymous
        self.assertTrue(self.holds(cond, self.root))

    def test_perm_list_needs_them_all(self):
        cond = {'perm': ['demoapp.view_country', 'demoapp.add_country']}
        self.assertFalse(self.holds(cond, self.viewer))
        self.assertTrue(self.holds(cond, make_user(
            'both', 'view_country', 'add_country')))

    def test_auth(self):
        cond = {'auth': 'tests.c6.staff'}
        self.assertTrue(self.holds(cond, self.staff))
        self.assertFalse(self.holds(cond, self.viewer))
        self.assertFalse(self.holds(cond))

    def test_auth_gets_the_object(self):
        mine = Country.objects.create(name='viewer')
        other = Country.objects.create(name='else')
        cond = {'auth': 'tests.c6.owner'}
        self.assertTrue(self.holds(cond, self.viewer, obj=mine))
        self.assertFalse(self.holds(cond, self.viewer, obj=other))

    def test_unknown_auth_is_false_and_logged(self):
        with self.assertLogs('djgentelella.authorization', 'ERROR') as logs:
            self.assertFalse(self.holds({'auth': 'tests.c6.nobody'}, self.root))
        self.assertIn('tests.c6.nobody', logs.output[0])

    def test_auth_that_raises_is_false_and_logged(self):
        with self.assertLogs('djgentelella.authorization', 'ERROR'):
            self.assertFalse(self.holds({'auth': 'tests.c6.broken'}, self.root))

    def test_group(self):
        self.assertTrue(self.holds({'group': 'Finanzas'}, self.staff))
        self.assertFalse(self.holds({'group': 'Ventas'}, self.staff))
        self.assertTrue(self.holds({'group': ['Ventas', 'Finanzas']}, self.staff))
        self.assertFalse(self.holds({'group': 'Finanzas'}))  # anonymous

    def test_setting_equals_and_in(self):
        set_settings('c6_mode', 'abierto')
        self.assertTrue(self.holds({'setting': 'c6_mode', 'equals': 'abierto'}))
        self.assertFalse(self.holds({'setting': 'c6_mode', 'equals': 'cerrado'}))
        self.assertTrue(self.holds({'setting': 'c6_mode', 'in': ['x', 'abierto']}))
        self.assertFalse(self.holds({'setting': 'c6_mode', 'in': []}))
        self.assertFalse(self.holds({'setting': 'c6_missing', 'equals': ''}))

    def test_setting_numbers_and_booleans_compare_as_text(self):
        set_settings('c6_count', '3')
        set_settings('c6_on', 'True')
        self.assertTrue(self.holds({'setting': 'c6_count', 'equals': 3}))
        self.assertTrue(self.holds({'setting': 'c6_on', 'equals': True}))
        self.assertFalse(self.holds({'setting': 'c6_on', 'equals': False}))

    def test_setting_by_site_with_global_fallback(self):
        set_settings('c6_mode', 'abierto')
        set_settings('c6_mode', 'cerrado', site=self.site_a)
        cond = {'setting': 'c6_mode', 'equals': 'abierto'}
        self.assertTrue(self.holds(cond, host='testserver'))
        self.assertFalse(self.holds(cond, host='a.test'))
        self.assertTrue(self.holds(cond, host='b.test'))

    def test_flag(self):
        self.assertFalse(self.holds({'flag': 'c6_beta'}))  # never set: off
        set_flag('c6_beta', True)
        self.assertTrue(self.holds({'flag': 'c6_beta'}))

    def test_user_attr(self):
        self.assertTrue(self.holds({'user_attr': 'is_staff'}, self.staff))
        self.assertFalse(self.holds({'user_attr': 'is_staff'}, self.viewer))
        self.assertTrue(self.holds({'user_attr': 'is_superuser'}, self.root))
        self.assertTrue(self.holds({'user_attr': 'is_authenticated'}, self.viewer))
        self.assertFalse(self.holds({'user_attr': 'is_authenticated'}))

    def test_user_attr_only_reads_the_safe_ones(self):
        with self.assertLogs('djgentelella.authorization', 'ERROR'):
            self.assertFalse(self.holds({'user_attr': 'is_active'}, self.viewer))
        with self.assertLogs('djgentelella.authorization', 'ERROR'):
            self.assertFalse(self.holds({'user_attr': 'password'}, self.viewer))

    def test_all_any_not(self):
        self.assertTrue(self.holds({'all': []}))
        self.assertFalse(self.holds({'any': []}))
        self.assertTrue(self.holds({'not': {'user_attr': 'is_authenticated'}}))
        self.assertTrue(self.holds({'all': [{'user_attr': 'is_staff'},
                                            {'group': 'Finanzas'}]}, self.staff))
        self.assertFalse(self.holds({'all': [{'user_attr': 'is_staff'},
                                             {'group': 'Ventas'}]}, self.staff))
        self.assertTrue(self.holds({'any': [{'group': 'Ventas'},
                                            {'user_attr': 'is_staff'}]}, self.staff))

    def test_the_contract_example(self):
        set_settings('modo', 'abierto')
        cond = {'all': [
            {'perm': 'demoapp.view_country'},
            {'auth': 'tests.c6.staff'},
            {'any': [{'group': 'Ventas'}, {'setting': 'modo', 'equals': 'abierto'}]},
            {'not': {'flag': 'beta_reportes'}},
        ]}
        user = make_user('full', 'view_country', staff=True)
        self.assertTrue(self.holds(cond, user))
        set_flag('beta_reportes', True)
        self.assertFalse(self.holds(cond, user))
        set_flag('beta_reportes', False)
        set_settings('modo', 'cerrado')
        self.assertFalse(self.holds(cond, user))
        self.assertFalse(self.holds(cond, self.viewer))  # not staff
        self.assertFalse(self.holds(cond))  # anonymous

    def test_nested_with_anonymous(self):
        cond = {'any': [{'not': {'any': [{'user_attr': 'is_authenticated'},
                                         {'group': 'Finanzas'}]}},
                        {'perm': 'demoapp.view_country'}]}
        self.assertTrue(self.holds(cond))  # anonymous: the not holds
        self.assertTrue(self.holds(cond, self.viewer))  # the perm
        self.assertFalse(self.holds(cond, self.staff))

    def test_invalid_is_false_and_logged(self):
        for cond in ({}, {'perm': 'x', 'auth': 'y'}, {'bogus': 1}, 'perm', [],
                     {'all': 'x'}, {'setting': 'k'}):
            with self.subTest(cond=cond):
                with self.assertLogs('djgentelella.authorization', 'ERROR'):
                    self.assertFalse(self.holds(cond, self.root))

    def test_the_structure_is_validated_once(self):
        cond = {'any': [{'perm': 'demoapp.view_country'},
                        {'user_attr': 'is_superuser'}]}
        auth_module._structure_cache.clear()
        with mock.patch.object(auth_module, 'validate_condition',
                               wraps=auth_module.validate_condition) as spy:
            for _ in range(3):
                self.assertTrue(self.holds(cond, self.viewer))
                # The same condition, rebuilt with its keys in another order.
                self.assertTrue(self.holds(
                    {'any': [{'user_attr': 'is_superuser'},
                             {'perm': 'demoapp.view_country'}][::-1]},
                    self.root))
        self.assertEqual(spy.call_count, 1)

    def test_cached_validation_keeps_json_types_apart(self):
        auth_module._structure_cache.clear()
        self.assertTrue(self.holds({'any': [{'perm': 'demoapp.view_country'}]},
                                   self.viewer))
        # A tuple is not a JSON list: it stays invalid after the list was cached.
        with self.assertLogs('djgentelella.authorization', 'ERROR'):
            self.assertFalse(self.holds(
                {'any': ({'perm': 'demoapp.view_country'},)}, self.viewer))
        # An invalid condition is logged on every evaluation, cached or not.
        for _ in range(2):
            with self.assertLogs('djgentelella.authorization', 'ERROR'):
                self.assertFalse(self.holds({'all': 'x'}, self.root))

    def test_without_a_request_the_user_is_anonymous(self):
        self.assertTrue(evaluate_condition({'not': {'user_attr': 'is_staff'}}, None))
        self.assertFalse(evaluate_condition({'perm': 'demoapp.view_country'}, None))

    def test_condition_request_stands_in_for_a_request(self):
        set_flag('c6_beta', True, site=self.site_a)
        request = ConditionRequest(self.viewer, self.site_a)
        self.assertTrue(evaluate_condition({'flag': 'c6_beta'}, request))
        self.assertTrue(evaluate_condition({'perm': 'demoapp.view_country'},
                                           request))
        system = ConditionRequest()
        self.assertFalse(system.user.is_authenticated)
        self.assertFalse(evaluate_condition({'flag': 'c6_beta'}, system))


class ValidateConditionTests(ConditionCase):
    def test_valid(self):
        for cond in (None, {'perm': 'demoapp.view_country'},
                     {'perm': ['a.b', 'c.d']}, {'auth': 'tests.c6.staff'},
                     {'group': 'x'}, {'group': ['x', 'y']},
                     {'setting': 'k', 'equals': 'v'}, {'setting': 'k', 'in': [1, 'a']},
                     {'flag': 'beta.reportes-2'}, {'user_attr': 'is_superuser'},
                     {'all': []}, {'any': [{'not': {'flag': 'x'}}]}):
            with self.subTest(cond=cond):
                self.assertEqual(validate_condition(cond), [])

    def test_errors_carry_the_path(self):
        cond = {'all': [
            {'perm': 'view_country'},
            {'any': [{'group': 'x'}, {'auth': 'tests.c6.nobody'}]},
            {'not': {'user_attr': 'is_active'}},
            {'setting': 'k'},
        ]}
        errors = validate_condition(cond)
        self.assertEqual([error.path for error in errors], [
            '$.all[0].perm', '$.all[1].any[1].auth', '$.all[2].not.user_attr',
            '$.all[3]'])
        self.assertIn('unknown authorization', errors[1].message)
        self.assertEqual(validate_condition({'flag': 1}, '$.root.props.condition'),
                         [('$.root.props.condition.flag', 'must be a flag name')])

    def test_invalid_shapes(self):
        cases = {
            'not an object': ['x'],
            'empty': {},
            'two kinds': {'perm': 'a.b', 'group': 'g'},
            'unknown kind': {'role': 'x'},
            'extra key': {'flag': 'x', 'equals': 'y'},
            'all not a list': {'all': {'flag': 'x'}},
            'not of a list': {'not': [{'flag': 'x'}]},
            'empty perm list': {'perm': []},
            'empty group': {'group': ''},
            'both operators': {'setting': 'k', 'equals': 'a', 'in': ['a']},
            'in not a list': {'setting': 'k', 'in': 'a'},
            'equals an object': {'setting': 'k', 'equals': {'a': 1}},
            'bad flag': {'flag': 'no spaces'},
        }
        for name, cond in cases.items():
            with self.subTest(name):
                self.assertNotEqual(validate_condition(cond), [])

    def test_depth_is_limited(self):
        cond = {'flag': 'x'}
        for _level in range(auth_module.MAX_DEPTH + 2):
            cond = {'not': cond}
        errors = validate_condition(cond)
        self.assertEqual(len(errors), 1)
        self.assertIn('nest', errors[0].message)

    def test_names_can_be_left_unchecked(self):
        self.assertEqual(validate_condition({'auth': 'tests.c6.nobody'},
                                            check_names=False), [])

    def test_registry(self):
        self.assertIn('tests.c6.staff', get_authorizations())
        with self.assertRaises(ImproperlyConfigured):
            authorization('')


class RequestCacheTests(ConditionCase):
    def setUp(self):
        super().setUp()
        self.staff = make_user('boss', staff=True)

    def test_once_per_request(self):
        request = make_request(self.staff)
        for _attempt in range(3):
            self.assertTrue(check_authorization('tests.c6.staff', request))
        self.assertTrue(evaluate_condition({'all': [{'auth': 'tests.c6.staff'}] * 2},
                                           request))
        self.assertEqual(CALLS, [('staff', None)])
        check_authorization('tests.c6.staff', make_request(self.staff))
        self.assertEqual(len(CALLS), 2, 'another request runs it again')

    def test_cached_per_object(self):
        request = make_request(self.staff)
        first = Country.objects.create(name='boss')
        second = Country.objects.create(name='other')
        self.assertTrue(check_authorization('tests.c6.owner', request, first))
        self.assertFalse(check_authorization('tests.c6.owner', request, second))
        self.assertTrue(check_authorization('tests.c6.owner', request, first))
        self.assertFalse(check_authorization('tests.c6.owner', request, second))
        self.assertEqual(CALLS, [('owner', first), ('owner', second)])

    def test_unsaved_objects_are_not_cached(self):
        request = make_request(self.staff)
        unsaved = Country(name='boss')
        check_authorization('tests.c6.owner', request, unsaved)
        check_authorization('tests.c6.owner', request, unsaved)
        self.assertEqual(len(CALLS), 2)

    def test_cache_false(self):
        request = make_request(self.staff)
        check_authorization('tests.c6.fresh', request)
        check_authorization('tests.c6.fresh', request)
        self.assertEqual(CALLS, [('fresh', None), ('fresh', None)])

    def test_a_new_user_on_the_same_request_is_asked_again(self):
        request = make_request(self.staff)
        self.assertTrue(check_authorization('tests.c6.staff', request))
        request.user = AnonymousUser()
        self.assertFalse(check_authorization('tests.c6.staff', request))

    def test_groups_are_read_once_per_request(self):
        user = make_user('member', groups=[self.finance])
        request = make_request(user)
        self.assertTrue(evaluate_condition({'group': 'Finanzas'}, request))
        with self.assertNumQueries(0):
            self.assertTrue(evaluate_condition({'group': 'Finanzas'}, request))
            self.assertFalse(evaluate_condition({'group': 'Ventas'}, request))


@override_settings(ALLOWED_HOSTS=HOSTS)
class SiteGroupsTests(ConditionCase):
    def test_default_is_every_group_of_the_user(self):
        user = make_user('member', groups=[self.finance, self.sales])
        self.assertEqual(set(site_groups(user, self.site_a)),
                         {self.finance, self.sales})
        self.assertEqual(list(site_groups(AnonymousUser(), None)), [])

    @override_settings(
        GT_SITE_GROUPS_RESOLVER='djgentelella.tests.Authorization_Test.only_finance')
    def test_resolver_setting(self):
        user = make_user('member', groups=[self.finance, self.sales])
        self.assertEqual(list(site_groups(user, self.site_a)), [self.finance])
        cond = {'group': 'Ventas'}
        self.assertFalse(evaluate_condition(cond, make_request(user, 'a.test')))
        self.assertTrue(evaluate_condition(cond, make_request(user, 'b.test')))


@override_settings(ALLOWED_HOSTS=HOSTS)
class FlagTests(ConditionCase):
    def test_off_until_set(self):
        self.assertFalse(flag_enabled('c6_new', make_request()))
        self.assertIsNone(flag_value('c6_new'))

    def test_global_and_site_with_fallback(self):
        set_flag('c6_beta', True)
        set_flag('c6_beta', False, site=self.site_a)
        self.assertTrue(flag_enabled('c6_beta', make_request(host='testserver')))
        self.assertFalse(flag_enabled('c6_beta', make_request(host='a.test')))
        self.assertTrue(flag_enabled('c6_beta', make_request(host='b.test')),
                        'b.test has no value of its own: the global one')
        self.assertTrue(flag_enabled('c6_beta'))
        self.assertFalse(flag_enabled('c6_beta', site=self.site_a))

    def test_site_only(self):
        set_flag('c6_beta', True, site=self.site_b)
        self.assertTrue(flag_enabled('c6_beta', make_request(host='b.test')))
        self.assertFalse(flag_enabled('c6_beta', make_request(host='a.test')))
        self.assertFalse(flag_enabled('c6_beta', make_request()))

    def test_stored_as_settings_with_the_prefix(self):
        set_flag('c6_beta', True, site=self.site_a)
        row = GentelellaSettings.objects.get(key__startswith='flag.')
        self.assertEqual((row.key, row.value, row.site), ('flag.c6_beta', 'true',
                                                          self.site_a))
        # A value written by hand in the settings admin counts too.
        GentelellaSettings.objects.create(key='flag.c6_manual', value='1')
        self.assertTrue(flag_enabled('c6_manual'))

    def test_none_returns_a_site_to_the_global_value(self):
        set_flag('c6_beta', True)
        set_flag('c6_beta', False, site=self.site_a)
        self.assertFalse(flag_enabled('c6_beta', site=self.site_a))
        set_flag('c6_beta', None, site=self.site_a)
        self.assertTrue(flag_enabled('c6_beta', site=self.site_a))
        self.assertIsNone(flag_value('c6_beta', self.site_a))

    def test_toggling_is_seen_at_once(self):
        request = make_request(host='a.test')
        set_flag('c6_beta', True, site=self.site_a)
        self.assertTrue(flag_enabled('c6_beta', request))
        set_flag('c6_beta', False, site=self.site_a)
        self.assertFalse(flag_enabled('c6_beta', request))

    def test_names(self):
        set_flag('c6_b', True)
        set_flag('c6_a', False, site=self.site_a)
        set_flag('c6_b', False, site=self.site_a)
        set_settings('not_a_flag', 'x')
        self.assertEqual(flag_names(), ['c6_a', 'c6_b'])

    def test_invalid_names(self):
        for name in ('', 'with space', 'x' * 96, None, '<script>'):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    set_flag(name, True)


class FlagAdminTests(ConditionCase):
    url = '/admin/djgentelella/gentelellasettings/flags/'

    def setUp(self):
        super().setUp()
        self.admin = make_user('admin', staff=True, superuser=True)
        self.client.force_login(self.admin)

    def test_listed_with_a_toggle_per_site(self):
        set_flag('c6_beta', True)
        set_flag('c6_beta', False, site=self.site_a)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        rows = response.context['rows']
        self.assertEqual([row['name'] for row in rows], ['c6_beta'])
        cells = {cell['site'].domain if cell['site'] else None:
                 (cell['stored'], cell['effective']) for cell in rows[0]['cells']}
        self.assertEqual(cells[None], (True, True))
        self.assertEqual(cells['a.test'], (False, False))
        self.assertEqual(cells['b.test'], (None, True))
        self.assertContains(response, 'inherited')
        changelist = self.client.get('/admin/djgentelella/gentelellasettings/')
        self.assertContains(changelist, self.url)

    def test_toggle(self):
        set_flag('c6_beta', True)
        response = self.client.post(self.url, {'name': 'c6_beta', 'state': 'off',
                                               'site': self.site_a.pk})
        self.assertRedirects(response, self.url)
        self.assertFalse(flag_enabled('c6_beta', site=self.site_a))
        self.client.post(self.url, {'name': 'c6_beta', 'state': 'inherit',
                                    'site': self.site_a.pk})
        self.assertIsNone(flag_value('c6_beta', self.site_a))
        self.client.post(self.url, {'name': 'c6_new', 'state': 'on', 'site': ''})
        self.assertTrue(flag_enabled('c6_new'))

    def test_bad_input_changes_nothing(self):
        for data in ({'name': 'bad name', 'state': 'on', 'site': ''},
                     {'name': 'c6_x', 'state': 'maybe', 'site': ''},
                     {'name': 'c6_x', 'state': 'on', 'site': '99999'},
                     {'name': 'c6_x', 'state': 'on', 'site': 'abc'}):
            with self.subTest(data=data):
                response = self.client.post(self.url, data)
                self.assertEqual(response.status_code, 302)
        self.assertFalse(GentelellaSettings.objects.filter(
            key__startswith='flag.').exists())

    def test_rows_that_are_no_flag_are_skipped(self):
        GentelellaSettings.objects.create(key='flag.<b>x', value='true')
        set_flag('c6_beta', True)
        response = self.client.get(self.url)
        self.assertEqual([row['name'] for row in response.context['rows']],
                         ['c6_beta'])
        self.assertNotContains(response, '<b>x')

    def test_needs_permissions(self):
        clerk = make_user('clerk', staff=True)
        self.client.force_login(clerk)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        viewer = make_user('viewer', 'view_gentelellasettings', staff=True)
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.post(self.url, {
            'name': 'c6_x', 'state': 'on', 'site': ''}).status_code, 403)
        self.assertFalse(GentelellaSettings.objects.filter(
            key__startswith='flag.').exists())
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)


# -- views -------------------------------------------------------------------------

class StaffAPIView(APIView):
    permission_classes = [ConditionPermission]
    condition = {'user_attr': 'is_staff'}

    def get(self, request):
        return Response({'ok': True})


class UndeclaredAPIView(APIView):
    permission_classes = [ConditionPermission]

    def get(self, request):
        return Response({'ok': True})


class MethodAPIView(APIView):
    permission_classes = [ConditionPermission]
    conditions_by_action = {'get': None, 'post': {'user_attr': 'is_staff'}}

    def get(self, request):
        return Response({'ok': True})

    def post(self, request):
        return Response({'ok': True})


class CountryViewSet(viewsets.ViewSet):
    permission_classes = [ConditionPermission]
    conditions_by_action = {
        'list': {'user_attr': 'is_authenticated'},
        'retrieve': {'auth': 'tests.c6.owner'},
    }

    def list(self, request):
        return Response([])

    def retrieve(self, request, pk=None):
        country = Country.objects.get(pk=pk)
        self.check_object_permissions(request, country)
        return Response({'name': country.name})


class ConditionPermissionTests(ConditionCase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.staff = make_user('boss', staff=True)
        self.clerk = make_user('clerk')

    def call(self, view, user=None, method='get', **kwargs):
        request = getattr(self.factory, method)('/')
        if user is not None:
            force_authenticate(request, user)
        return view(request, **kwargs)

    def test_condition(self):
        view = StaffAPIView.as_view()
        self.assertEqual(self.call(view, self.staff).status_code, 200)
        self.assertEqual(self.call(view, self.clerk).status_code, 403)
        self.assertIn(self.call(view).status_code, (401, 403))

    def test_nothing_declared_is_refused(self):
        self.assertEqual(self.call(UndeclaredAPIView.as_view(),
                                   self.staff).status_code, 403)

    def test_by_method_on_an_api_view(self):
        view = MethodAPIView.as_view()
        self.assertEqual(self.call(view, self.clerk).status_code, 200)
        self.assertEqual(self.call(view, self.clerk, 'post').status_code, 403)
        self.assertEqual(self.call(view, self.staff, 'post').status_code, 200)
        self.assertEqual(self.call(view, self.staff, 'put').status_code, 403,
                         'a method missing from the map is refused')

    def test_by_action_and_object(self):
        mine = Country.objects.create(name='clerk')
        other = Country.objects.create(name='else')
        list_view = CountryViewSet.as_view({'get': 'list'})
        detail = CountryViewSet.as_view({'get': 'retrieve'})
        self.assertEqual(self.call(list_view, self.clerk).status_code, 200)
        self.assertIn(self.call(list_view).status_code, (401, 403))
        self.assertEqual(self.call(detail, self.clerk, pk=mine.pk).status_code, 200)
        self.assertEqual(self.call(detail, self.clerk, pk=other.pk).status_code, 403)

    def test_unmapped_action_is_refused(self):
        view = CountryViewSet.as_view({'get': 'list'})
        permission = ConditionPermission()
        fake = mock.Mock(action='destroy', conditions_by_action={'list': None})
        self.assertFalse(permission.has_permission(make_request(self.staff), fake))
        self.assertEqual(self.call(view, self.staff).status_code, 200)


class StaffView(ConditionRequiredMixin, View):
    condition = {'user_attr': 'is_staff'}

    def get(self, request):
        return HttpResponse('ok')


class NoConditionView(ConditionRequiredMixin, View):
    def get(self, request):
        return HttpResponse('ok')


class OwnerView(ConditionRequiredMixin, View):
    condition = {'auth': 'tests.c6.owner'}

    def get_condition_object(self):
        return Country.objects.get(pk=self.kwargs['pk'])

    def get(self, request, pk):
        return HttpResponse('ok')


@condition_required({'user_attr': 'is_staff'})
def staff_function_view(request):
    """Only for staff."""
    return HttpResponse('ok')


@condition_required({'user_attr': 'is_staff'}, raise_exception=True)
def strict_function_view(request):
    return HttpResponse('ok')


class DjangoViewTests(ConditionCase):
    def setUp(self):
        super().setUp()
        self.staff = make_user('boss', staff=True)
        self.clerk = make_user('clerk')

    def test_mixin(self):
        view = StaffView.as_view()
        self.assertEqual(view(make_request(self.staff)).status_code, 200)
        with self.assertRaises(PermissionDenied):
            view(make_request(self.clerk))
        response = view(make_request(path='/secret/'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=/secret/', response['Location'])

    def test_mixin_needs_a_condition(self):
        with self.assertRaises(ImproperlyConfigured):
            NoConditionView.as_view()(make_request(self.staff))

    def test_mixin_with_an_object(self):
        mine = Country.objects.create(name='clerk')
        other = Country.objects.create(name='else')
        view = OwnerView.as_view()
        self.assertEqual(view(make_request(self.clerk), pk=mine.pk).status_code, 200)
        with self.assertRaises(PermissionDenied):
            view(make_request(self.clerk), pk=other.pk)

    def test_decorator(self):
        self.assertEqual(staff_function_view(make_request(self.staff)).status_code,
                         200)
        with self.assertRaises(PermissionDenied):
            staff_function_view(make_request(self.clerk))
        response = staff_function_view(make_request(path='/x/'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(staff_function_view.__name__, 'staff_function_view')
        self.assertEqual(staff_function_view.__doc__, 'Only for staff.')

    def test_decorator_raise_exception(self):
        with self.assertRaises(PermissionDenied):
            strict_function_view(make_request())

    def test_decorator_refuses_an_invalid_condition(self):
        with self.assertRaises(ImproperlyConfigured):
            condition_required({'user_attr': 'password'})


# -- templates and menus -------------------------------------------------------------

@override_settings(ALLOWED_HOSTS=HOSTS)
class TemplateTagTests(ConditionCase):
    def setUp(self):
        super().setUp()
        self.staff = make_user('boss', staff=True)

    def render(self, text, user=None, host='testserver', **context):
        template = Template('{% load gtauthorization %}' + text)
        return template.render(Context({'request': make_request(user, host),
                                        **context}))

    def test_if_condition(self):
        text = '{% if_condition cond %}yes{% else %}no{% endif_condition %}'
        cond = {'user_attr': 'is_staff'}
        self.assertEqual(self.render(text, self.staff, cond=cond), 'yes')
        self.assertEqual(self.render(text, cond=cond), 'no')
        self.assertEqual(self.render(text, cond=None), 'yes')
        with self.assertLogs('djgentelella.authorization', 'ERROR'):
            self.assertEqual(self.render(text, cond='not json'), 'no')

    def test_if_condition_with_json_and_an_object(self):
        country = Country.objects.create(name='boss')
        text = ('{% if_condition \'{"auth": "tests.c6.owner"}\' country %}'
                'mine{% endif_condition %}')
        self.assertEqual(self.render(text, self.staff, country=country), 'mine')
        self.assertEqual(self.render(text, country=country), '')

    def test_if_flag(self):
        text = '{% if_flag "c6_beta" %}beta{% else %}stable{% endif_flag %}'
        self.assertEqual(self.render(text), 'stable')
        set_flag('c6_beta', True, site=self.site_a)
        self.assertEqual(self.render(text, host='a.test'), 'beta')
        self.assertEqual(self.render(text), 'stable')
        self.assertEqual(self.render('{% if_flag name %}x{% endif_flag %}',
                                     name='bad name'), '')

    def test_authorized_filter_and_tag(self):
        text = '{% if request|authorized:"tests.c6.staff" %}staff{% endif %}'
        self.assertEqual(self.render(text, self.staff), 'staff')
        self.assertEqual(self.render(text), '')
        country = Country.objects.create(name='boss')
        text = ('{% authorized_for "tests.c6.owner" country as ok %}{{ ok }}'
                '{% condition_holds cond as holds %}{{ holds }}'
                '{% flag_on "c6_beta" as on %}{{ on }}')
        self.assertEqual(self.render(text, self.staff, country=country,
                                     cond={'user_attr': 'is_staff'}),
                         'TrueTrueFalse')

    def test_syntax(self):
        with self.assertRaises(TemplateSyntaxError):
            Template('{% load gtauthorization %}'
                     '{% if_condition %}{% endif_condition %}')
        with self.assertRaises(TemplateSyntaxError):
            Template('{% load gtauthorization %}{% if_flag a b %}{% endif_flag %}')


class MenuConditionTests(ConditionCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.plain = MenuItem.objects.create(title='Plain item', url_name='/plain',
                                            category='main', position=0)
        cls.staff_only = MenuItem.objects.create(
            title='Staff item', url_name='/staff', category='main', position=1,
            condition={'user_attr': 'is_staff'})
        cls.beta = MenuItem.objects.create(
            title='Beta item', url_name='/beta', category='sidebar',
            condition={'flag': 'c6_menu_beta'})
        MenuItem.objects.create(title='Beta child', url_name='/beta/child',
                                category='sidebar', parent=cls.beta)
        cls.both = MenuItem.objects.create(
            title='Perm and condition', url_name='/both', category='main',
            position=2, condition={'user_attr': 'is_staff'})
        cls.both.permission.add(Permission.objects.get(codename='view_country'))

    def render(self, tag, user=None):
        template = Template('{% load gentelellamenu %}{% ' + tag + ' %}')
        return template.render(Context({'request': make_request(user)}))

    def test_without_condition_as_before(self):
        self.assertIsNone(self.plain.condition)
        self.assertIn('Plain item', self.render('top_menu'))
        self.assertIn('Plain item', self.render('top_menu', make_user('clerk')))

    def test_condition(self):
        self.assertNotIn('Staff item', self.render('top_menu'))
        self.assertIn('Staff item', self.render('top_menu', make_user(
            'boss', staff=True)))

    def test_permissions_and_condition(self):
        self.assertNotIn('Perm and condition', self.render('top_menu', make_user(
            'boss', staff=True)))
        self.assertNotIn('Perm and condition', self.render('top_menu', make_user(
            'viewer', 'view_country')))
        self.assertIn('Perm and condition', self.render('top_menu', make_user(
            'both', 'view_country', staff=True)))

    def test_a_hidden_item_hides_its_children(self):
        html = self.render('sidebar_menu')
        self.assertNotIn('Beta item', html)
        self.assertNotIn('Beta child', html)
        set_flag('c6_menu_beta', True)
        html = self.render('sidebar_menu')
        self.assertIn('Beta item', html)
        self.assertIn('Beta child', html)

    def test_admin_form_validates_the_condition(self):
        data = {'title': 'x', 'url_name': '/x', 'category': 'main', 'position': 0,
                'condition': '{"auth": "tests.c6.nobody"}'}
        form = MenuItemForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn('unknown authorization', str(form.errors['condition']))
        form = MenuItemForm({**data, 'condition': '{"user_attr": "is_staff"}'})
        self.assertTrue(form.is_valid(), form.errors)
        form = MenuItemForm({**data, 'condition': ''})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data['condition'])


# -- flows and designs -------------------------------------------------------------

class ConditionFlow(Flow):
    name = 'tests.c6.flow'
    model = Country
    states = [('draft', 'Draft'), ('done', 'Done')]
    initial = 'draft'
    transitions = [
        Transition('approve', 'draft', 'done', condition={'all': [
            {'perm': 'demoapp.change_country'}, {'flag': 'c6_approvals'}]}),
    ]


@override_settings(ALLOWED_HOSTS=HOSTS)
class FlowConditionTests(ConditionCase):
    def setUp(self):
        super().setUp()
        self.flow = ConditionFlow()
        self.country = Country.objects.create(name='Chile')
        self.approve = self.flow.get_transition('approve')

    def test_evaluated_for_the_user_without_a_request(self):
        editor = make_user('editor', 'change_country')
        self.assertFalse(self.flow.can_run(self.approve, self.country, editor))
        set_flag('c6_approvals', True)
        self.assertTrue(self.flow.can_run(self.approve, self.country, editor))
        self.assertFalse(self.flow.can_run(self.approve, self.country,
                                           make_user('clerk')))

    def test_publish_rejects_invalid_conditions(self):
        document = {
            'schema_version': 2, 'name': 'tests.c6.json', 'model': 'demoapp.Country',
            'initial': 'a', 'states': [
                {'id': 'a'}, {'id': 'b'},
                {'id': 's', 'type': 'switch', 'cases': [
                    {'condition': {'auth': 'tests.c6.nobody'}, 'target': 'a'}],
                 'default': 'b'}],
            'transitions': [{'name': 'go', 'source': 'a', 'target': 's',
                             'condition': {'user_attr': 'password'}}],
        }
        with self.assertRaises(ImproperlyConfigured) as raised:
            publish_definition(document)
        self.assertIn('$.transitions[0].condition.user_attr', str(raised.exception))
        self.assertIn('$.states[2].cases[0].condition.auth', str(raised.exception))
        document['transitions'][0]['condition'] = {'user_attr': 'is_staff'}
        document['states'][2]['cases'][0]['condition'] = {'auth': 'tests.c6.staff'}
        self.assertEqual(publish_definition(document).version, 1)


class DesignConditionTests(DesignState, ConditionCase):
    def setUp(self):
        super().setUp()
        register(EchoComponent)
        self.user = make_user('ana')
        self.client.force_login(self.user)

    def publish(self, *nodes):
        page, errors = publishing.publish(design(*nodes), path='sample')
        self.assertEqual(errors, [])
        return page

    def get(self):
        return self.client.get('/designs/sample/').content.decode()

    def test_props_and_meta_condition(self):
        self.publish(
            node('html', 'always', {'html': '<p>always</p>'}),
            node('html', 'beta', {'html': '<p>beta only</p>',
                                  'condition': {'flag': 'c6_beta'}}),
            {**node('html', 'stable', {'html': '<p>stable only</p>'}),
             'meta': {'condition': {'not': {'flag': 'c6_beta'}}}},
        )
        content = self.get()
        self.assertIn('always', content)
        self.assertNotIn('beta only', content)
        self.assertIn('stable only', content)
        set_flag('c6_beta', True)
        content = self.get()
        self.assertIn('beta only', content)
        self.assertNotIn('stable only', content)

    def test_children_and_media_go_with_the_node(self):
        self.publish(node('html', 'top', {'html': '<p>top</p>'}))
        page, errors = publishing.publish({
            **design(), 'root': node('page', 'page', children=[
                node('row', 'main', {'condition': {'user_attr': 'is_staff'}}, [
                    node('col', 'body', {'width': 12}, [
                        node('echo', 'hello', {'message': 'secret echo'})])])])},
            path='sample')
        self.assertEqual(errors, [])
        content = self.get()
        self.assertNotIn('secret echo', content)
        self.assertNotIn('echo.js', content)
        self.assertNotIn('window.echo_hello', content)
        self.user.is_staff = True
        self.user.save()
        content = self.get()
        self.assertIn('secret echo', content)
        self.assertIn('window.echo_hello', content)

    def test_endpoints_of_hidden_nodes_are_not_served(self):
        page = self.publish(node('echo', 'hello', {
            'message': 'hi', 'condition': {'user_attr': 'is_staff'}}))
        url = '/gtapis/designs/%d/hello/' % page.pk
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(url + 'shout/').status_code, 404)
        self.user.is_staff = True
        self.user.save()
        self.assertEqual(self.client.get(url).json()['message'], 'hi')

    def test_endpoints_under_a_hidden_ancestor(self):
        page, errors = publishing.publish({
            **design(), 'root': node('page', 'page', children=[
                {**node('row', 'main', children=[
                    node('col', 'body', {'width': 12}, [
                        node('echo', 'hello', {'message': 'hi'})])]),
                 'meta': {'condition': {'flag': 'c6_beta'}}}])}, path='sample')
        self.assertEqual(errors, [])
        url = '/gtapis/designs/%d/hello/' % page.pk
        self.assertEqual(self.client.get(url).status_code, 404)
        set_flag('c6_beta', True)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_the_component_does_not_see_the_condition(self):
        # EchoComponent's props_schema has additionalProperties: false.
        cond = {'flag': 'c6_beta'}
        resolved, errors = engine.resolve(design(node('echo', 'hello', {
            'message': 'hi', 'condition': cond})))
        self.assertEqual(errors, [])
        hello = resolved.nodes['hello']
        self.assertEqual(hello.build.props, {'message': 'hi'})
        self.assertEqual((hello.condition, hello.conditions), (cond, (cond,)))
        self.assertEqual(resolved.nodes['body'].conditions, ())

    def test_invalid_conditions_are_publishing_errors(self):
        page, errors = publishing.publish(design(
            node('html', 'a', {'html': '', 'condition': {'auth': 'tests.c6.nobody'}}),
            {**node('html', 'b', {'html': ''}), 'meta': {'condition': {'flag': 1}}},
            {**node('html', 'c', {'html': '', 'condition': {'flag': 'x'}}),
             'meta': {'condition': {'flag': 'y'}}},
        ), path='sample')
        self.assertIsNone(page)
        paths = [error.path for error in errors]
        body = '$.root.children[0].children[0].children'
        self.assertIn('%s[0].props.condition.auth' % body, paths)
        self.assertIn('%s[1].meta.condition.flag' % body, paths)
        self.assertIn('%s[2]' % body, paths)
        # The shape of meta is the envelope's.
        page, errors = publishing.publish(design(
            {**node('html', 'd', {'html': ''}), 'meta': {'condition': 'flag'}}),
            path='sample')
        self.assertEqual([error.path for error in errors],
                         ['%s[0].meta.condition' % body])
