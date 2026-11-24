"""Optimistic locking (``djgentelella.locking``, contract C9): the version of
an object, the form mixin, ``CRUDView.optimistic_lock``, the DRF mixin and
the ``optimistic_lock`` prop of the ``object_management`` design component.

Everything is opt-in: the tests marked "off" prove that without the option
the HTML, the responses and the number of queries do not change."""

import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django import forms
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import include, path, reverse
from django.utils import timezone
from rest_framework import permissions, serializers, viewsets
from rest_framework.test import APIRequestFactory, force_authenticate

from demo.urls import urlpatterns as demo_urlpatterns
from demoapp.models import Country, DigitalSignature, Person, Product
from djgentelella import locking
from djgentelella.authorization import authorization
from djgentelella.cruds.base import CRUDView
from djgentelella.designs import engine, factories
from djgentelella.locking import (
    OptimisticLockFormMixin, OptimisticLockMixin, lock_form_class, object_version,
    parse_if_match,
)
from djgentelella.tests.Designs_Test import design
from djgentelella.tests.DesignsData_Test import (
    ALL_PRODUCT_PERMS, DataDesignTestCase, product_form, table,
)
from djgentelella.tests.DesignsHooks_Test import gtconfig


__all__ = ['LockingVersionTests', 'LockingFormTests', 'LockingCRUDViewTests',
           'LockingAPITests', 'LockingObjectManagementTests']

CSRF = re.compile(r'(name="csrfmiddlewaretoken" value=")[^"]*"')


def without_csrf(content):
    """The page without its CSRF token, masked differently on each request."""
    return CSRF.sub(r'\1"', content)


def lock_meta(field):
    return type('GTLockMeta', (), {'version_field': field})


# -- object_version ------------------------------------------------------------------

class LockingVersionTests(TestCase):
    def setUp(self):
        self.country = Country.objects.create(name='Costa Rica', code='cr')
        self.person = Person.objects.create(
            name='Ana', num_children=2, country=self.country,
            born_date=date(1990, 1, 2),
            last_time=datetime(2024, 5, 6, 7, 8, 9, tzinfo=dt_timezone.utc))

    def test_a_checksum_of_the_editable_fields(self):
        version = object_version(self.person)
        self.assertRegex(version, r'^[0-9a-f]{40}$')
        # Read again from the database: the same version.
        self.assertEqual(object_version(Person.objects.get(pk=self.person.pk)),
                         version)
        for field, value in (('name', 'Beto'), ('num_children', 3),
                             ('born_date', date(1990, 1, 3))):
            other = Person.objects.get(pk=self.person.pk)
            setattr(other, field, value)
            self.assertNotEqual(object_version(other), version, field)

    def test_a_foreign_key_counts_by_its_id(self):
        version = object_version(self.person)
        self.person.country = Country.objects.create(name='Panamá')
        self.assertNotEqual(object_version(self.person), version)

    def test_the_order_of_the_fields_does_not_matter(self):
        version = object_version(self.person)
        fields = locking.version_fields(Person)
        with mock.patch.object(locking, 'version_fields',
                               return_value=list(reversed(fields))):
            self.assertEqual(object_version(self.person), version)

    def test_the_primary_key_and_the_not_editable_fields_are_left_out(self):
        names = [f.name for f in locking.version_fields(DigitalSignature)]
        self.assertEqual(names, ['filename', 'file'])
        self.assertNotIn('id', [f.name for f in locking.version_fields(Person)])

    def test_a_file_is_its_stored_name(self):
        sig = DigitalSignature(filename='a.pdf', file='digital_signature/a.pdf')
        version = object_version(sig)
        sig.file = 'digital_signature/b.pdf'
        self.assertNotEqual(object_version(sig), version)

    def test_many_to_many_are_left_out(self):
        product = Product.objects.create(name='Saw', price=Decimal('1.00'))
        version = object_version(product)
        from_db = Product.objects.get(pk=product.pk)
        from_db.tags.create(name='red')
        self.assertEqual(object_version(from_db), version)

    def test_stable_between_processes(self):
        """Not ``hash()``: another interpreter (another PYTHONHASHSEED) gets
        the same checksum for the same values."""
        script = (
            'import django, os, sys;'
            'os.environ.setdefault("DJANGO_SETTINGS_MODULE", "demo.settings");'
            'django.setup();'
            'from django.utils.crypto import salted_hmac;'
            'import json;'
            'from djgentelella import locking;'
            'payload = json.dumps(json.loads(sys.argv[1]), cls=locking._Encoder,'
            ' sort_keys=True, separators=(",", ":"));'
            'print(salted_hmac(locking._SALT, payload, algorithm="sha256")'
            '.hexdigest()[:40])')
        values = {f.attname: f.value_from_object(self.person)
                  for f in locking.version_fields(Person)}
        raw = json.dumps(values, cls=locking._Encoder)
        outputs = set()
        for seed in ('1', '2'):
            result = subprocess.run(
                [sys.executable, '-c', script, raw], capture_output=True, text=True,
                env={**os.environ, 'PYTHONHASHSEED': seed}, check=True)
            outputs.add(result.stdout.strip())
        self.assertEqual(outputs, {object_version(self.person)})

    def test_keyed_with_the_secret_key(self):
        version = object_version(self.person)
        with override_settings(SECRET_KEY='another-secret-key-for-the-test-123'):
            self.assertNotEqual(object_version(self.person), version)

    def test_no_queries(self):
        person = Person.objects.get(pk=self.person.pk)
        with self.assertNumQueries(0):
            object_version(person)

    def test_with_an_integer_version_field(self):
        with mock.patch.object(Person, 'GTLockMeta', lock_meta('num_children'),
                               create=True):
            self.assertEqual(object_version(self.person), '2')
            self.person.name = 'Changed, but not the version'
            self.assertEqual(object_version(self.person), '2')
            self.person.num_children = 3
            self.assertEqual(object_version(self.person), '3')

    def test_with_an_auto_now_version_field(self):
        sig = DigitalSignature.objects.create(filename='a.pdf', file='a.pdf')
        with mock.patch.object(DigitalSignature, 'GTLockMeta', lock_meta('updated'),
                               create=True):
            version = object_version(sig)
            self.assertEqual(version, sig.updated.isoformat())
            sig.filename = 'b.pdf'
            sig.save()
            self.assertNotEqual(object_version(sig), version)

    def test_a_version_field_that_is_not_a_field(self):
        with mock.patch.object(Person, 'GTLockMeta', lock_meta('nope'), create=True):
            with self.assertRaises(ImproperlyConfigured):
                object_version(self.person)

    def test_parse_if_match(self):
        self.assertIsNone(parse_if_match(None))
        self.assertIsNone(parse_if_match(''))
        self.assertEqual(parse_if_match('"abc"'), {'abc'})
        self.assertEqual(parse_if_match('W/"abc", "def"'), {'abc', 'def'})
        self.assertEqual(parse_if_match('*'), {'*'})
        self.assertEqual(parse_if_match('abc'), {'abc'})


# -- the form mixin ------------------------------------------------------------------

class PersonForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = ['name', 'num_children', 'country', 'born_date', 'last_time']


LockedPersonForm = lock_form_class(PersonForm)


@override_settings(LANGUAGE_CODE='en')
class LockingFormTests(TestCase):
    def setUp(self):
        self.country = Country.objects.create(name='Costa Rica')
        self.person = Person.objects.create(
            name='Ana', num_children=2, country=self.country,
            born_date=date(1990, 1, 2), last_time=timezone.now())
        self.editor = User.objects.create_user('beto', first_name='Beto',
                                               last_name='Solís')

    def data(self, form, **changes):
        values = {name: form[name].value() for name in form.fields}
        values['last_time'] = form.initial['last_time'].strftime('%Y-%m-%d %H:%M:%S')
        values.update(changes)
        return values

    def test_lock_form_class(self):
        self.assertTrue(issubclass(LockedPersonForm, OptimisticLockFormMixin))
        self.assertTrue(issubclass(LockedPersonForm, PersonForm))
        self.assertIs(lock_form_class(LockedPersonForm), LockedPersonForm)

    def test_the_hidden_field_carries_the_version(self):
        form = LockedPersonForm(instance=self.person)
        self.assertIn('_version', form.fields)
        self.assertTrue(form['_version'].is_hidden)
        self.assertEqual(form['_version'].value(), object_version(self.person))
        self.assertIn('name="_version"', str(form))
        # Creating: no object, no version.
        self.assertNotIn('_version', LockedPersonForm().fields)

    def test_accepts_the_current_version(self):
        form = LockedPersonForm(instance=self.person)
        bound = LockedPersonForm(self.data(form, name='Ana María'),
                                 instance=Person.objects.get(pk=self.person.pk))
        self.assertTrue(bound.is_valid(), bound.errors)
        self.assertFalse(bound.version_conflict)
        bound.save()
        self.person.refresh_from_db()
        self.assertEqual(self.person.name, 'Ana María')

    def test_refuses_an_old_version(self):
        form = LockedPersonForm(instance=self.person)
        data = self.data(form, name='Mine')
        Person.objects.filter(pk=self.person.pk).update(name='Theirs')
        bound = LockedPersonForm(data, instance=Person.objects.get(pk=self.person.pk))
        self.assertFalse(bound.is_valid())
        self.assertTrue(bound.version_conflict)
        self.assertEqual([e.code for e in bound.non_field_errors().as_data()],
                         ['version_conflict'])
        self.assertIn('changed by someone else', bound.non_field_errors()[0])
        # Not linked to a field.
        self.assertNotIn('_version', bound.errors)

    def test_says_who_and_when_from_the_history(self):
        form = LockedPersonForm(instance=self.person)
        data = self.data(form, name='Mine')
        Person.objects.filter(pk=self.person.pk).update(name='Theirs')
        LogEntry.objects.create(
            user=self.editor, content_type=ContentType.objects.get_for_model(Person),
            object_id=str(self.person.pk), object_repr='Ana', action_flag=CHANGE,
            change_message='changed')
        bound = LockedPersonForm(data, instance=Person.objects.get(pk=self.person.pk))
        self.assertFalse(bound.is_valid())
        self.assertIn('Last change: Beto Solís', bound.non_field_errors()[0])

    def test_a_deleted_object(self):
        form = LockedPersonForm(instance=self.person)
        data = self.data(form)
        instance = Person.objects.get(pk=self.person.pk)
        Person.objects.filter(pk=self.person.pk).delete()
        bound = LockedPersonForm(data, instance=instance)
        self.assertFalse(bound.is_valid())
        self.assertIn('deleted', bound.non_field_errors()[0])

    def test_no_history_query_without_a_conflict(self):
        form = LockedPersonForm(instance=self.person)
        bound = LockedPersonForm(self.data(form),
                                 instance=Person.objects.get(pk=self.person.pk))
        with CaptureQueriesContext(connection) as queries:
            self.assertTrue(bound.is_valid())
        sql = ' '.join(q['sql'] for q in queries.captured_queries)
        self.assertNotIn('django_admin_log', sql)
        self.assertNotIn('django_content_type', sql)
        # The row read again (and the country of the select).
        self.assertEqual(sql.count('FROM "demoapp_person"'), 1)

    def test_without_a_version(self):
        form = LockedPersonForm(instance=self.person)
        data = self.data(form, _version='')
        Person.objects.filter(pk=self.person.pk).update(name='Theirs')
        bound = LockedPersonForm(data, instance=Person.objects.get(pk=self.person.pk))
        self.assertTrue(bound.is_valid(), bound.errors)

        class Required(LockedPersonForm):
            optimistic_lock_required = True
        bound = Required(data, instance=Person.objects.get(pk=self.person.pk))
        self.assertFalse(bound.is_valid())
        self.assertEqual([e.code for e in bound.non_field_errors().as_data()],
                         ['version_required'])

    def test_the_row_is_locked_inside_a_transaction(self):
        form = LockedPersonForm(instance=self.person)
        bound = LockedPersonForm(self.data(form),
                                 instance=Person.objects.get(pk=self.person.pk))
        with mock.patch('django.db.models.query.QuerySet.select_for_update',
                        autospec=True, side_effect=lambda qs, *a, **k: qs) as lock:
            self.assertTrue(bound.is_valid())
        # TestCase runs every test inside a transaction.
        self.assertEqual(lock.call_count, 1)


# -- CRUDView ------------------------------------------------------------------------

DENY = {'auth': 'tests.locking.never'}


@authorization('tests.locking.never')
def never(request, obj=None):
    return False


class LockedProductCRUD(CRUDView):
    model = Product
    namespace = 'locked'
    fields = ['name', 'price', 'status']
    optimistic_lock = True


class PlainProductCRUD(CRUDView):
    model = Product
    namespace = 'plain'
    fields = ['name', 'price', 'status']


class DeniedProductCRUD(LockedProductCRUD):
    namespace = 'denied'
    action_conditions = {'update': DENY}


urlpatterns = demo_urlpatterns + [
    path('locking-tests/locked/', include((LockedProductCRUD().get_urls(), 'locked'))),
    path('locking-tests/plain/', include((PlainProductCRUD().get_urls(), 'plain'))),
    path('locking-tests/denied/', include((DeniedProductCRUD().get_urls(), 'denied'))),
]


def crud_url(namespace, product):
    return reverse('%s:demoapp_product_update' % namespace, args=[product.pk])


@override_settings(ROOT_URLCONF=__name__, LANGUAGE_CODE='en')
class LockingCRUDViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ana', password='pw')
        for codename in ('view_product', 'change_product', 'add_product',
                         'delete_product'):
            self.user.user_permissions.add(Permission.objects.get(
                content_type__app_label='demoapp', codename=codename))
        self.client.force_login(self.user)
        self.product = Product.objects.create(name='Saw', price=Decimal('10.00'),
                                              status='draft')

    def post_data(self, **changes):
        return {'name': 'Saw', 'price': '10.00', 'status': 'draft', **changes}

    def test_the_form_carries_the_version(self):
        response = self.client.get(crud_url('locked', self.product))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="_version"')
        self.assertContains(response, 'value="%s"' % object_version(self.product))
        self.assertNotContains(response, 'gt-version-conflict')

    def test_saves_with_the_current_version(self):
        version = object_version(self.product)
        response = self.client.post(crud_url('locked', self.product),
                                    self.post_data(name='Big saw', _version=version))
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Big saw')

    def test_refuses_an_old_version(self):
        version = object_version(self.product)
        Product.objects.filter(pk=self.product.pk).update(name='Theirs')
        response = self.client.post(crud_url('locked', self.product),
                                    self.post_data(name='Mine', _version=version))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].version_conflict)
        self.assertContains(response, 'changed by someone else')
        self.assertContains(response, 'gt-version-reload')
        self.assertContains(response, 'href="%s?"' % crud_url('locked', self.product))
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Theirs')

    def test_the_condition_comes_before_the_version(self):
        version = object_version(self.product)
        Product.objects.filter(pk=self.product.pk).update(name='Theirs')
        response = self.client.post(crud_url('denied', self.product),
                                    self.post_data(name='Mine', _version=version))
        self.assertEqual(response.status_code, 403)

    def test_off_by_default(self):
        self.assertFalse(CRUDView.optimistic_lock)
        response = self.client.get(crud_url('plain', self.product))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '_version')
        self.assertNotIn(OptimisticLockFormMixin,
                         type(response.context['form']).__mro__)
        # An old version is not even read.
        version = object_version(self.product)
        Product.objects.filter(pk=self.product.pk).update(name='Theirs')
        response = self.client.post(crud_url('plain', self.product),
                                    self.post_data(name='Mine', _version=version))
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Mine')

    def test_off_the_same_queries_and_html(self):
        """The plain view does what a CRUDView did before this option: the
        same HTML as the locked one minus the version, and the queries of
        the same view on master."""
        plain = without_csrf(
            self.client.get(crud_url('plain', self.product)).content.decode())
        locked = without_csrf(
            self.client.get(crud_url('locked', self.product)).content.decode())
        hidden = re.compile(r'<input type="hidden" name="_version" value="%s"[^>]*>'
                            % object_version(self.product))
        self.assertRegex(locked, hidden)

        def normal(content):
            return re.sub(r'\s+', ' ', content)
        self.assertEqual(normal(hidden.sub('', locked).replace('locked', 'plain')),
                         normal(plain))
        with CaptureQueriesContext(connection) as queries:
            self.client.post(crud_url('plain', self.product),
                             self.post_data(name='Mine'))
        sql = [q['sql'] for q in queries.captured_queries]
        # Measured with the same view on master (42cc7859): 6.
        self.assertEqual(len(sql), 6)
        self.assertFalse([q for q in sql if 'FOR UPDATE' in q or 'SAVEPOINT' in q])
        with CaptureQueriesContext(connection) as locked_queries:
            self.client.post(crud_url('locked', self.product),
                             self.post_data(name='Mine again',
                                            _version=object_version(
                                                Product.objects.get(
                                                    pk=self.product.pk))))
        # The locked view adds the read of the row (and its savepoint).
        self.assertGreater(len(locked_queries.captured_queries), len(sql))


# -- DRF ------------------------------------------------------------------------------

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'status']


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]


class LockedProductViewSet(OptimisticLockMixin, ProductViewSet):
    pass


class RequiredProductViewSet(LockedProductViewSet):
    optimistic_lock_required = True


class NoUpdates(permissions.BasePermission):
    def has_permission(self, request, view):
        return view.action not in ('update', 'partial_update')


class DeniedProductViewSet(LockedProductViewSet):
    permission_classes = [NoUpdates]


@override_settings(LANGUAGE_CODE='en')
class LockingAPITests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user('ana')
        self.product = Product.objects.create(name='Saw', price=Decimal('10.00'),
                                              status='draft')
        self.payload = {'name': 'Big saw', 'price': '11.00', 'status': 'active'}

    def call(self, viewset, method, action, data=None, **headers):
        view = viewset.as_view({method: action})
        request = getattr(self.factory, method)(
            '/', data, format='json',
            **{'HTTP_' + key.upper().replace('-', '_'): value
               for key, value in headers.items()})
        force_authenticate(request, self.user)
        return view(request, pk=self.product.pk)

    def put(self, viewset=LockedProductViewSet, data=None, **headers):
        return self.call(viewset, 'put', 'update', data or self.payload, **headers)

    def test_the_detail_has_an_etag(self):
        response = self.call(LockedProductViewSet, 'get', 'retrieve')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['ETag'], '"%s"' % object_version(self.product))
        self.assertNotIn('_version', response.data)

    def test_if_match_current(self):
        response = self.put(if_match='"%s"' % object_version(self.product))
        self.assertEqual(response.status_code, 200, response.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Big saw')
        # The answer carries the new version.
        self.assertEqual(response['ETag'], '"%s"' % object_version(self.product))

    def test_if_match_old(self):
        version = object_version(self.product)
        Product.objects.filter(pk=self.product.pk).update(name='Theirs')
        response = self.put(if_match='"%s"' % version)
        self.assertEqual(response.status_code, 409)
        current = object_version(Product.objects.get(pk=self.product.pk))
        self.assertEqual(response.data['code'], 'version_conflict')
        self.assertEqual(response.data['version'], current)
        self.assertIn('changed by someone else', response.data['detail'])
        self.assertEqual(response['ETag'], '"%s"' % current)
        self.assertEqual(Product.objects.get(pk=self.product.pk).name, 'Theirs')

    def test_the_version_in_the_body(self):
        version = object_version(self.product)
        response = self.put(data={**self.payload, '_version': version})
        self.assertEqual(response.status_code, 200)
        response = self.put(data={**self.payload, 'name': 'Again',
                                  '_version': version})
        self.assertEqual(response.status_code, 409)

    def test_if_match_wins_over_the_body(self):
        version = object_version(self.product)
        response = self.put(data={**self.payload, '_version': 'old'},
                            if_match='"%s"' % version)
        self.assertEqual(response.status_code, 200)

    def test_patch(self):
        version = object_version(self.product)
        Product.objects.filter(pk=self.product.pk).update(status='retired')
        response = self.call(LockedProductViewSet, 'patch', 'partial_update',
                             {'name': 'Mine'}, if_match='"%s"' % version)
        self.assertEqual(response.status_code, 409)
        current = object_version(Product.objects.get(pk=self.product.pk))
        response = self.call(LockedProductViewSet, 'patch', 'partial_update',
                             {'name': 'Mine'}, if_match='"%s"' % current)
        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        # PATCH saved over the fresh row: the other change is kept.
        self.assertEqual((self.product.name, self.product.status),
                         ('Mine', 'retired'))

    def test_any_version(self):
        Product.objects.filter(pk=self.product.pk).update(name='Theirs')
        self.assertEqual(self.put(if_match='*').status_code, 200)

    def test_absent(self):
        Product.objects.filter(pk=self.product.pk).update(name='Theirs')
        self.assertEqual(self.put().status_code, 200)

    def test_absent_and_required(self):
        response = self.put(RequiredProductViewSet)
        self.assertEqual(response.status_code, 428)
        self.assertEqual(response.data['code'], 'version_required')
        response = self.put(RequiredProductViewSet,
                            if_match='"%s"' % object_version(self.product))
        self.assertEqual(response.status_code, 200)

    def test_order_403_409_400(self):
        version = object_version(self.product)
        Product.objects.filter(pk=self.product.pk).update(name='Theirs')
        bad = {'name': '', 'price': 'x', 'status': 'nope'}
        # A refused update with an old version and bad data: 403.
        self.assertEqual(self.put(DeniedProductViewSet, bad,
                                  if_match='"%s"' % version).status_code, 403)
        # Allowed, old version, bad data: 409.
        self.assertEqual(self.put(data=bad, if_match='"%s"' % version).status_code,
                         409)
        # Allowed, current version, bad data: 400.
        current = object_version(Product.objects.get(pk=self.product.pk))
        self.assertEqual(self.put(data=bad, if_match='"%s"' % current).status_code,
                         400)

    def test_a_missing_object_is_404(self):
        self.product.delete()
        self.product.pk = 999999
        self.assertEqual(self.put(if_match='"x"').status_code, 404)

    def test_off_without_the_mixin(self):
        Product.objects.filter(pk=self.product.pk).update(name='Theirs')
        response = self.call(ProductViewSet, 'get', 'retrieve')
        self.assertNotIn('ETag', response)
        response = self.put(ProductViewSet, if_match='"old"')
        self.assertEqual(response.status_code, 200)


# -- object_management ----------------------------------------------------------------

@authorization('tests.locking.not_the_hammer')
def not_the_hammer(request, obj=None):
    return obj is None or obj.name != 'Hammer'


class LockingObjectManagementTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        self.grant(*ALL_PRODUCT_PERMS)

    def page(self, path='products', **props):
        page = self.publish(design(table(**props), forms=product_form()), path=path)
        return page, self.api(page, 'products')

    def payload(self, **changes):
        return {'name': 'Rye bread', 'price': '4.00', 'status': 'draft',
                'category': self.food.pk, **changes}

    def test_the_prop_is_validated(self):
        self.assertEqual(self.errors(design(table(optimistic_lock=True),
                                            forms=product_form())), [])
        errors = self.errors(design(table(optimistic_lock='yes'),
                                    forms=product_form()))
        self.assertEqual(len(errors), 1)
        self.assertIn('optimistic_lock', errors[0])

    def test_the_viewset_gets_the_mixin(self):
        def viewset(**props):
            resolved, errors = engine.resolve(design(table(**props),
                                                     forms=product_form()))
            self.assertEqual(errors, [])
            build = resolved.nodes['products'].build
            return build, factories.management_viewset_for(build)
        build, locked = viewset(optimistic_lock=True)
        self.assertTrue(build.optimistic_lock)
        self.assertTrue(issubclass(locked, OptimisticLockMixin))
        # After ManagementMixin: its get_object() (the conditions) runs first.
        mro = locked.__mro__
        self.assertLess(mro.index(factories.ManagementMixin),
                        mro.index(OptimisticLockMixin))
        for props in ({}, {'optimistic_lock': False}):
            build, plain = viewset(**props)
            self.assertFalse(build.optimistic_lock)
            self.assertFalse(issubclass(plain, OptimisticLockMixin))

    def test_values_for_update_carry_the_version(self):
        _page, url = self.page(optimistic_lock=True)
        response = self.client.get(url + '%d/get_values_for_update/' % self.bread.pk)
        version = object_version(Product.objects.get(pk=self.bread.pk))
        self.assertEqual(response.json()['_version'], version)
        self.assertEqual(response['ETag'], '"%s"' % version)
        response = self.client.get(url + '%d/' % self.bread.pk)
        self.assertEqual(response['ETag'], '"%s"' % version)
        self.assertNotIn('_version', response.json())

    def test_an_old_version_is_409_and_the_current_saves(self):
        _page, url = self.page(optimistic_lock=True)
        detail = url + '%d/' % self.bread.pk
        version = self.client.get(detail + 'get_values_for_update/').json()['_version']
        Product.objects.filter(pk=self.bread.pk).update(name='Whole bread')
        response = self.post_json(detail, self.payload(_version=version), method='put')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['code'], 'version_conflict')
        current = self.client.get(detail + 'get_values_for_update/').json()
        self.assertEqual(current['name'], 'Whole bread')
        response = self.post_json(detail, self.payload(_version=current['_version']),
                                  method='put')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Product.objects.get(pk=self.bread.pk).name, 'Rye bread')

    def test_the_row_condition_comes_before_the_version(self):
        _page, url = self.page(
            optimistic_lock=True,
            action_conditions={'update': {'auth': 'tests.locking.not_the_hammer'}})
        detail = url + '%d/' % self.hammer.pk
        response = self.post_json(detail, self.payload(_version='old'), method='put')
        self.assertEqual(response.status_code, 403)
        # Another row, the same old version: now it is the version.
        response = self.post_json(url + '%d/' % self.bread.pk,
                                  self.payload(_version='old'), method='put')
        self.assertEqual(response.status_code, 409)

    def test_off_without_the_prop(self):
        """Without the prop (or with it false) the page, the API and the
        number of queries are those of before."""
        _page, url = self.page()
        content = without_csrf(self.client.get(
            reverse('gt-design-page', args=['products'])).content.decode())
        detail = url + '%d/' % self.bread.pk
        values = self.client.get(detail + 'get_values_for_update/')
        self.assertNotIn('_version', values.json())
        self.assertNotIn('ETag', values)
        self.assertNotIn('ETag', self.client.get(detail))
        response = self.post_json(detail, self.payload(_version='old'), method='put')
        self.assertEqual(response.status_code, 200)
        with CaptureQueriesContext(connection) as off_queries:
            self.post_json(detail, self.payload(name='Again'), method='put')
        # Measured with the same page on master (42cc7859): 10.
        self.assertEqual(len(off_queries.captured_queries), 10)

        factories.clear_cache()
        _page, url = self.page(optimistic_lock=False)
        self.assertEqual(without_csrf(self.client.get(
            reverse('gt-design-page', args=['products'])).content.decode()), content)
        detail = url + '%d/' % self.bread.pk
        with CaptureQueriesContext(connection) as false_queries:
            self.post_json(detail, self.payload(name='Once more'), method='put')
        self.assertEqual(len(false_queries.captured_queries),
                         len(off_queries.captured_queries))
        self.assertFalse([q for q in false_queries.captured_queries
                          if 'FOR UPDATE' in q['sql']])

        # With the prop, the page is the same too: the version travels in
        # the API, not in the HTML.
        factories.clear_cache()
        self.page(optimistic_lock=True)
        locked = without_csrf(self.client.get(
            reverse('gt-design-page', args=['products'])).content.decode())
        self.assertEqual(gtconfig(locked, 'products'), gtconfig(content, 'products'))
        self.assertEqual(locked, content)
