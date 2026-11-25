import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import signing
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.forms import formset_factory
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from django.utils.html import escape
from django.utils.translation import gettext_lazy

from djgentelella.forms.dynamic import (
    SIGNING_SALT,
    When,
    serialize_rules,
    server_methods,
    unsign_method,
)
from djgentelella.forms.forms import GTForm, GTFormSet
from djgentelella.widgets import core as genwidgets

from .dynamic_snapshot_forms import SNAPSHOT_RENDERS, snapshot_renders

#: Each test signs users in: a fast hasher keeps it from spending seconds
#: per test hashing their passwords (PBKDF2).
FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

SNAPSHOTS = Path(__file__).parent / 'snapshots'


class PedidoForm(GTForm):
    grid_representation = [[['tipo', 'razon_social'], ['cedula_juridica']]]

    tipo = forms.ChoiceField(choices=[('persona', 'P'), ('empresa', 'E')])
    razon_social = forms.CharField(required=False)
    cedula_juridica = forms.CharField(required=False)
    pais = forms.CharField(required=False)
    provincia = forms.CharField(required=False)
    cantidad = forms.IntegerField(required=False)
    precio = forms.DecimalField(required=False)
    total = forms.DecimalField(required=False)
    descuento = forms.IntegerField(required=False)
    estado = forms.CharField(required=False)
    observaciones = forms.CharField(required=False)
    oculto = forms.CharField(required=False, widget=genwidgets.HiddenInput)

    dynamic_actions = [
        When('tipo').equals('empresa').show('razon_social', 'cedula_juridica')
        .require('cedula_juridica'),
        When('tipo').not_equals('empresa').hide('razon_social', 'cedula_juridica'),
        When('pais').changes().refresh('provincia'),
        When('cantidad', 'precio').changes().set_value('total', server='calc_total'),
        When('descuento').gt(50).confirm(gettext_lazy('Discount above 50%?')),
        When('estado').in_('cerrado', 'anulado').disable('*').enable('observaciones'),
    ]

    def calc_total(self, data):
        cantidad = int(data.get('cantidad') or 0)
        precio = int(data.get('precio') or 0)
        if cantidad < 0:
            raise ValidationError('Negative quantity')
        return {'total': cantidad * precio, 'not_a_field': 'dropped'}

    def secret(self, data):
        return {'total': 'leaked'}


class PublicForm(GTForm):
    a = forms.IntegerField()
    b = forms.IntegerField()
    dynamic_actions_public = True
    dynamic_actions = [When('a').changes().set_value('b', server='double')]

    def double(self, data):
        return {'b': int(data.get('a') or 0) * 2}


class ArgsForm(GTForm):
    """A form whose __init__ needs an argument: it builds its own instance."""

    a = forms.CharField()
    dynamic_actions = [When('a').changes().set_value('a', server='upper')]

    def __init__(self, owner, *args, **kwargs):
        self.owner = owner
        super().__init__(*args, **kwargs)

    @classmethod
    def dynamic_actions_instance(cls, request):
        return cls(owner=request.user)

    def upper(self, data):
        return {'a': '%s:%s' % (self.owner.username, data.get('a', '').upper())}


class PermsForm(GTForm):
    a = forms.IntegerField()
    dynamic_actions_permissions = ['auth.view_group']
    dynamic_actions = [When('a').changes().set_value('a', server='same')]

    def same(self, data):
        return {'a': data.get('a')}


class HookForm(GTForm):
    """Only the user called 'boss' may run it: the page's own rule."""

    a = forms.IntegerField()
    dynamic_actions = [When('a').changes().set_value('a', server='same')]

    @classmethod
    def dynamic_actions_has_permission(cls, request, method):
        return request.user.username == 'boss' and method == 'same'

    def same(self, data):
        return {'a': data.get('a')}


class DropsFieldForm(GTForm):
    a = forms.CharField()
    b = forms.CharField()
    c = forms.CharField()
    dynamic_actions = [
        When('a').equals('x').show('b', 'c'),
        When('b').equals('y').show('c'),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields['b']


def rules_of(form):
    return serialize_rules(form, form.get_dynamic_actions())


def marker_rules(html):
    start = html.index('data-gt-dynamic="') + len('data-gt-dynamic="')
    end = html.index('"', start)
    raw = html[start:end]
    for entity, char in (('&quot;', '"'), ('&#x27;', "'"), ('&lt;', '<'),
                         ('&gt;', '>'), ('&amp;', '&')):
        raw = raw.replace(entity, char)
    return json.loads(raw)


# The confirm message is translated: the demo runs in Spanish.
@override_settings(LANGUAGE_CODE='en')
class DynamicDSLTest(SimpleTestCase):
    def test_serializes_the_example_of_the_stage(self):
        rules = rules_of(PedidoForm())
        self.assertEqual(rules[0], {
            'when': ['tipo'], 'trigger': 'equals', 'value': 'empresa',
            'actions': [
                {'action': 'show', 'fields': ['razon_social', 'cedula_juridica']},
                {'action': 'require', 'fields': ['cedula_juridica']},
            ]})
        self.assertEqual(rules[1]['trigger'], 'not_equals')
        self.assertEqual(rules[2], {
            'when': ['pais'], 'trigger': 'changes',
            'actions': [{'action': 'refresh', 'fields': ['provincia']}]})
        self.assertEqual(rules[3]['when'], ['cantidad', 'precio'])
        self.assertNotIn('value', rules[2])
        self.assertEqual(rules[4]['value'], 50)
        self.assertEqual(rules[4]['actions'],
                         [{'action': 'confirm', 'message': 'Discount above 50%?'}])
        self.assertEqual(rules[5]['value'], ['cerrado', 'anulado'])

    def test_wildcard_is_every_visible_field_but_the_rule_sources(self):
        disable = rules_of(PedidoForm())[5]['actions'][0]
        self.assertEqual(disable['action'], 'disable')
        self.assertNotIn('estado', disable['fields'])
        self.assertNotIn('oculto', disable['fields'])
        self.assertIn('observaciones', disable['fields'])
        self.assertEqual(len(disable['fields']), len(PedidoForm.base_fields) - 2)

    def test_server_action_carries_a_signed_reference(self):
        action = rules_of(PedidoForm())[3]['actions'][0]
        self.assertEqual(action['fields'], ['total'])
        path, method = unsign_method(action['server'])
        self.assertEqual(path, '%s.PedidoForm' % __name__)
        self.assertEqual(method, 'calc_total')
        self.assertEqual(server_methods(PedidoForm), {'calc_total'})

    def test_every_trigger(self):
        cases = [
            (When('a').changes(), 'changes', None),
            (When().on_load(), 'on_load', None),
            (When('a').equals(3), 'equals', 3),
            (When('a').not_equals('x'), 'not_equals', 'x'),
            (When('a').in_('x', 'y'), 'in', ['x', 'y']),
            (When('a').gt(1.5), 'gt', 1.5),
            (When('a').lt(2), 'lt', 2),
            (When('a').is_empty(), 'is_empty', None),
            (When('a').is_checked(), 'is_checked', None),
        ]

        class AForm(GTForm):
            a = forms.CharField()
            b = forms.CharField()

        form = AForm()
        for rule, trigger, value in cases:
            data = rule.show('b').serialize(form)
            self.assertEqual(data['trigger'], trigger)
            self.assertEqual(data.get('value'), value)

    def test_every_action(self):
        class AForm(GTForm):
            a = forms.CharField()
            b = forms.CharField()

        rule = (When('a').changes().show('b').hide('b').enable('b').disable('b')
                .require('b').refresh('b').add_class('x', 'b')
                .remove_class('y', 'b').set_value('b', 'v')
                .set_value('b', from_field='a').call('fn', 1, 'two'))
        actions = rule.serialize(AForm())['actions']
        self.assertEqual([a['action'] for a in actions], [
            'show', 'hide', 'enable', 'disable', 'require', 'refresh', 'add_class',
            'remove_class', 'set_value', 'set_value', 'call'])
        self.assertEqual(actions[6]['css'], 'x')
        self.assertEqual(actions[8]['value'], 'v')
        self.assertEqual(actions[9]['from'], 'a')
        self.assertEqual(actions[10], {'action': 'call', 'name': 'fn',
                                       'args': [1, 'two']})

    def test_rule_mistakes_are_caught_when_declared(self):
        with self.assertRaises(ValueError):
            When('a').equals(1).changes()
        with self.assertRaises(TypeError):
            When('a').gt('10')
        with self.assertRaises(TypeError):
            When('a').equals(object())
        with self.assertRaises(ValueError):
            When('a').changes().set_value('b', 1, server='m')
        with self.assertRaises(ValueError):
            When('a').changes().set_value('b')
        with self.assertRaises(ValueError):
            When('a').changes().set_value('b', server='_private')
        with self.assertRaises(ValueError):
            When('a').changes().show()
        with self.assertRaises(ValueError):
            When('a').changes().refresh('*')
        with self.assertRaises(ValueError):
            When().changes()
        with self.assertRaises(TypeError):
            When(1)

    def test_rule_without_trigger_or_actions(self):
        form = PedidoForm()
        with self.assertRaises(ImproperlyConfigured):
            When('tipo').show('total').serialize(form)
        with self.assertRaises(ImproperlyConfigured):
            When('tipo').changes().serialize(form)

    def test_unknown_field_is_a_configuration_error(self):
        with self.assertRaises(ImproperlyConfigured):
            When('tipo').changes().show('typo').serialize(PedidoForm())

    def test_a_field_the_instance_dropped_is_skipped(self):
        rules = rules_of(DropsFieldForm())
        self.assertEqual(rules, [{'when': ['a'], 'trigger': 'equals', 'value': 'x',
                                  'actions': [{'action': 'show', 'fields': ['c']}]}])

    def test_server_method_must_exist_and_be_declared_on_the_class(self):
        class Missing(GTForm):
            a = forms.CharField()
            dynamic_actions = [When('a').changes().set_value('a', server='nope')]

        with self.assertRaises(ImproperlyConfigured):
            Missing().as_plain()

        class PerInstance(GTForm):
            a = forms.CharField()

            def get_dynamic_actions(self):
                return [When('a').changes().set_value('a', server='m')]

            def m(self, data):
                return {}

        with self.assertRaises(ImproperlyConfigured):
            PerInstance().as_plain()

    def test_local_form_cannot_use_server_actions(self):
        class Local(GTForm):
            a = forms.CharField()
            dynamic_actions = [When('a').changes().set_value('a', server='m')]

            def m(self, data):
                return {}

        with self.assertRaises(ImproperlyConfigured):
            Local().as_plain()


class DynamicRenderTest(SimpleTestCase):
    def test_every_render_carries_the_rules(self):
        form = PedidoForm(prefix='p')
        for render in SNAPSHOT_RENDERS + ('as_div', '__str__', '__html__'):
            html = str(getattr(form, render)())
            self.assertEqual(html.count('class="gt-dynamic-actions"'), 1, render)
            self.assertIn('data-gt-dynamic-prefix="p"', html)
            self.assertIn('data-gt-dynamic-url="%s"' % reverse('gt-dynamic-action'),
                          html)
            self.assertEqual(marker_rules(html), rules_of(form))

    def test_fields_list_and_no_url_without_server_actions(self):
        class AForm(GTForm):
            a = forms.CharField()
            b = forms.CharField()
            dynamic_actions = [When('a').is_empty().hide('b')]

        html = AForm().as_horizontal()
        self.assertIn('data-gt-dynamic-prefix=""', html)
        self.assertIn('data-gt-dynamic-fields="[&quot;a&quot;, &quot;b&quot;]"', html)
        self.assertNotIn('data-gt-dynamic-url', html)

    def test_user_data_is_escaped(self):
        payload = '"><script>alert(1)</script>'

        class AForm(GTForm):
            a = forms.CharField()
            dynamic_actions = [When('a').equals(payload).confirm(payload)
                               .add_class('x" onclick="y', 'a')]

        html = AForm().as_plain()
        marker = html[html.index('<div class="gt-dynamic-actions"'):]
        self.assertNotIn('<script>', marker)
        self.assertNotIn('" onclick', marker)
        rules = marker_rules(html)
        self.assertEqual(rules[0]['value'], payload)
        self.assertEqual(rules[0]['actions'][0]['message'], payload)

    def test_formset_rows_and_empty_form_carry_their_prefix(self):
        formset = formset_factory(PedidoForm, formset=GTFormSet, extra=2)(prefix='f')
        html = formset.as_horizontal()
        self.assertIn('data-gt-dynamic-prefix="f-0"', html)
        self.assertIn('data-gt-dynamic-prefix="f-1"', html)
        self.assertIn('data-gt-dynamic-prefix="f-__prefix__"',
                      formset.empty_form.as_horizontal())

    def test_attrs_for_a_form_tag(self):
        attrs = PedidoForm().dynamic_actions_attrs
        self.assertTrue(attrs.startswith(' data-gt-dynamic="'))
        self.assertEqual(
            marker_rules('<form%s>' % attrs), rules_of(PedidoForm()))

    def test_message_follows_the_active_language(self):
        with translation.override('es'):
            rules = rules_of(PedidoForm())
        self.assertIsInstance(rules[4]['actions'][0]['message'], str)


class DynamicSnapshotTest(SimpleTestCase):
    """A form without dynamic_actions renders exactly what it did before."""

    def test_html_is_unchanged(self):
        with translation.override('en'):
            renders = snapshot_renders()
        self.assertEqual(
            sorted(renders), sorted(p.stem for p in SNAPSHOTS.glob('*.html')))
        for name, html in renders.items():
            with self.subTest(name):
                expected = (SNAPSHOTS / ('%s.html' % name)).read_text()
                self.assertEqual(html, expected)
                self.assertNotIn('gt-dynamic', html)

    def test_attrs_are_empty(self):
        class AForm(GTForm):
            a = forms.CharField()

        self.assertEqual(AForm().dynamic_actions_attrs, '')


class DynamicEndpointTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('dyn', password='x')
        self.client.force_login(self.user)
        self.url = reverse('gt-dynamic-action')
        self.token = rules_of(PedidoForm())[3]['actions'][0]['server']

    def post(self, body, client=None, raw=False):
        client = client or self.client
        return client.post(self.url, body if raw else json.dumps(body),
                           content_type='application/json')

    def test_runs_the_declared_method(self):
        response = self.post({'token': self.token,
                              'data': {'cantidad': '3', 'precio': '4'}})
        self.assertEqual(response.status_code, 200)
        # Keys that are not fields of the form are dropped.
        self.assertEqual(response.json(), {'total': 12})

    def test_rejects_an_invalid_signature(self):
        for token in (self.token[:-2] + 'xx', 'garbage',
                      signing.dumps({'form': '%s.PedidoForm' % __name__,
                                     'method': 'calc_total'}, salt='other')):
            with self.subTest(token):
                response = self.post({'token': token, 'data': {}})
                self.assertEqual(response.status_code, 403)

    def test_rejects_a_method_not_declared(self):
        token = signing.dumps({'form': '%s.PedidoForm' % __name__,
                               'method': 'secret'}, salt=SIGNING_SALT)
        response = self.post({'token': token, 'data': {}})
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('leaked', response.content.decode())

    def test_rejects_something_that_is_not_a_form(self):
        for path in ('os.path.join', 'no.such.Module', 'json.JSONDecoder'):
            token = signing.dumps({'form': path, 'method': 'calc_total'},
                                  salt=SIGNING_SALT)
            with self.subTest(path):
                self.assertEqual(self.post({'token': token}).status_code, 400)

    def test_malformed_payloads_are_400(self):
        token = self.token
        for body in ('not json', '[1, 2]', '"x"', json.dumps({'data': {}}),
                     json.dumps({'token': 1}),
                     json.dumps({'token': token, 'data': []}),
                     json.dumps({'token': token, 'data': {'a': {'b': 1}}}),
                     json.dumps({'token': token, 'data': {'a': [[1]]}}),
                     b'\xff\xfe'):
            with self.subTest(body):
                self.assertEqual(self.post(body, raw=True).status_code, 400)

    def test_malformed_signed_payload(self):
        token = signing.dumps(['a', 'b'], salt=SIGNING_SALT)
        self.assertEqual(self.post({'token': token}).status_code, 403)

    def test_validation_error_is_400(self):
        response = self.post({'token': self.token, 'data': {'cantidad': '-1'}})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'errors': ['Negative quantity']})

    def test_only_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_anonymous_is_refused_unless_the_form_is_public(self):
        anonymous = Client()
        self.assertEqual(self.post({'token': self.token}, anonymous).status_code, 403)
        token = rules_of(PublicForm())[0]['actions'][0]['server']
        response = self.post({'token': token, 'data': {'a': '21'}}, anonymous)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'b': 42})

    def test_csrf_is_enforced(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(self.post({'token': self.token}, client).status_code, 403)

    def test_form_builds_its_own_instance(self):
        token = rules_of(ArgsForm(owner=None))[0]['actions'][0]['server']
        response = self.post({'token': token, 'data': {'a': 'abc'}})
        self.assertEqual(response.json(), {'a': 'dyn:ABC'})


# English labels are asserted: the demo runs in Spanish once its .mo, which is
# not versioned, is compiled, and a local run would disagree with CI.
@override_settings(LANGUAGE_CODE='en')
@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class DynamicTokenTest(TestCase):
    """The set_value(server=...) token expires, binds to the user of the form
    when it has one, and the form class decides who may run its methods."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('dyn', password='x')
        self.other = get_user_model().objects.create_user('other', password='x')
        self.client.force_login(self.user)
        self.url = reverse('gt-dynamic-action')

    def post(self, token, data=None, client=None):
        return (client or self.client).post(
            self.url, json.dumps({'token': token, 'data': data or {}}),
            content_type='application/json')

    def token(self, form):
        return rules_of(form)[0]['actions'][0]['server']

    def test_expired_token_is_refused(self):
        with mock.patch('django.core.signing.time.time',
                        return_value=time.time() - 13 * 3600):
            old = self.token(PublicForm())
        response = self.post(old, {'a': '1'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(),
                         {'error': 'The form expired, reload the page.'})
        self.assertEqual(self.post(self.token(PublicForm()), {'a': '1'}).json(),
                         {'b': 2})
        with override_settings(GT_DYNAMIC_ACTIONS_MAX_AGE=None):
            self.assertEqual(self.post(old, {'a': '1'}).status_code, 200)
        with override_settings(GT_DYNAMIC_ACTIONS_MAX_AGE=14 * 3600):
            self.assertEqual(self.post(old, {'a': '1'}).status_code, 200)

    def test_token_is_bound_to_the_user_of_the_form(self):
        form = PublicForm()
        form.request = SimpleNamespace(user=self.user)
        token = self.token(form)
        self.assertEqual(signing.loads(token, salt=SIGNING_SALT)['user'],
                         str(self.user.pk))
        self.assertEqual(self.post(token, {'a': '2'}).json(), {'b': 4})
        other = Client()
        other.force_login(self.other)
        response = self.post(token, {'a': '2'}, other)
        self.assertEqual(response.status_code, 403)
        # Public, but rendered for a user: an anonymous client cannot reuse it.
        self.assertEqual(self.post(token, {'a': '2'}, Client()).status_code, 403)
        # Without a request (or with an anonymous one) nothing is bound.
        self.assertNotIn('user', signing.loads(self.token(PublicForm()),
                                               salt=SIGNING_SALT))

    def test_tokens_are_not_reusable_across_users_only_when_bound(self):
        # Two users render the same form: their tokens differ.
        a, b = PublicForm(), PublicForm()
        a.request = SimpleNamespace(user=self.user)
        b.request = SimpleNamespace(user=self.other)
        self.assertNotEqual(self.token(a), self.token(b))

    def test_permissions_of_the_form(self):
        token = self.token(PermsForm())
        self.assertEqual(self.post(token, {'a': '1'}).status_code, 403)
        self.user.user_permissions.add(Permission.objects.get(codename='view_group'))
        self.client.force_login(get_user_model().objects.get(pk=self.user.pk))
        self.assertEqual(self.post(token, {'a': '1'}).json(), {'a': '1'})
        self.assertEqual(self.post(token, {'a': '1'}, Client()).status_code, 403)

    def test_permission_hook(self):
        token = self.token(HookForm())
        self.assertEqual(self.post(token, {'a': '1'}).status_code, 403)
        boss = get_user_model().objects.create_user('boss', password='x')
        client = Client()
        client.force_login(boss)
        self.assertEqual(self.post(token, {'a': '1'}, client).json(), {'a': '1'})

    def test_default_hook(self):
        anonymous = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))
        self.assertFalse(PedidoForm.dynamic_actions_has_permission(anonymous, 'x'))
        self.assertTrue(PublicForm.dynamic_actions_has_permission(anonymous, 'x'))
        self.assertFalse(PermsForm.dynamic_actions_has_permission(anonymous, 'x'))
