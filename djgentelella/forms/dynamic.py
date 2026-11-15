"""Dynamic actions: what APEX calls Dynamic Actions, declared on the form.

A form lists its rules in ``dynamic_actions``; GTForm serializes them into a
``data-gt-dynamic`` attribute and ``gentelella/js/base/dynamic_actions.js``
runs them in the browser, so the developer writes no JavaScript::

    class PedidoForm(GTForm, forms.ModelForm):
        dynamic_actions = [
            When('tipo').equals('empresa').show('razon_social').require('razon_social'),
            When('pais').changes().refresh('provincia'),
            When('cantidad', 'precio').changes().set_value('total', server='calc'),
        ]

        def calc(self, data):                # runs on the server
            return {'total': ...}

A rule has one *trigger* and a list of *actions*:

* ``changes()`` runs every action each time one of the fields changes.
* ``on_load()`` runs every action once, when the form is initialised.
* ``equals``, ``not_equals``, ``in_``, ``gt``, ``lt``, ``is_empty`` and
  ``is_checked`` are conditions, evaluated on load and on every change of the
  fields (all of them must hold). While the condition holds the reversible
  actions (show/hide, enable/disable, require, add/remove class) are applied;
  when it stops holding they are undone, in reverse order. The other actions
  (``set_value``, ``refresh``, ``confirm``, ``call``) run only when a change
  makes the condition true.

``set_value(server=...)`` posts the form data to a generic endpoint. The
reference to the form method travels signed with :mod:`django.core.signing`,
and only methods declared in a rule of the class can be called. The token
expires after ``GT_DYNAMIC_ACTIONS_MAX_AGE`` seconds (12 hours by default) and,
when the form has a ``request`` attribute with an authenticated user, it is
bound to that user.
"""

import json
from decimal import Decimal

from django.conf import settings
from django.core import signing
from django.core.exceptions import ImproperlyConfigured
from django.core.serializers.json import DjangoJSONEncoder
from django.forms.utils import flatatt
from django.urls import NoReverseMatch, reverse
from django.utils.functional import Promise
from django.utils.html import format_html

SIGNING_SALT = 'djgentelella.forms.dynamic'
# Lifetime of a set_value(server=...) token, in seconds; None never expires.
DEFAULT_MAX_AGE = 60 * 60 * 12

CONDITIONS = ('equals', 'not_equals', 'in', 'gt', 'lt', 'is_empty', 'is_checked')
TRIGGERS = ('changes', 'on_load') + CONDITIONS
# Actions that can be undone when a condition stops holding.
REVERSIBLE = ('show', 'hide', 'enable', 'disable', 'require',
              'add_class', 'remove_class')
# Actions whose targets may be '*': every field of the form but the rule's own.
WILDCARD = ('show', 'hide', 'enable', 'disable', 'require',
            'add_class', 'remove_class')

_MISSING = object()


def _json_value(value):
    """``value`` as something json can carry, or TypeError."""
    if isinstance(value, Promise):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    raise TypeError('Dynamic actions only carry json scalars, got %r' % (value,))


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise TypeError('gt() and lt() compare with a number, got %r' % (value,))
    return float(value) if isinstance(value, Decimal) else value


def _names(fields, allow_wildcard=False):
    for name in fields:
        if not isinstance(name, str) or not name:
            raise TypeError('Field names are non empty strings, got %r' % (name,))
        if name == '*' and not allow_wildcard:
            raise ValueError("'*' is not a valid field here")
    return list(fields)


class When:
    """One dynamic action rule. Build it by chaining::

        When('estado').in_('cerrado', 'anulado').disable('*').enable('notas')
    """

    def __init__(self, *fields):
        self.fields = _names(fields)
        self.trigger = None
        self.value = None
        self.actions = []

    def __repr__(self):
        return 'When(%s).%s(%r) -> %s' % (
            ', '.join(self.fields), self.trigger, self.value,
            [action['action'] for action in self.actions])

    # -- triggers ------------------------------------------------------------
    def _trigger(self, name, value=None):
        if self.trigger is not None:
            raise ValueError('A rule has one trigger, it already has %r'
                             % self.trigger)
        if name != 'on_load' and not self.fields:
            raise ValueError('%s() needs at least one field in When()' % name)
        self.trigger = name
        self.value = value
        return self

    def changes(self):
        return self._trigger('changes')

    def on_load(self):
        return self._trigger('on_load')

    def equals(self, value):
        return self._trigger('equals', _json_value(value))

    def not_equals(self, value):
        return self._trigger('not_equals', _json_value(value))

    def in_(self, *values):
        return self._trigger('in', [_json_value(value) for value in values])

    def gt(self, value):
        return self._trigger('gt', _number(value))

    def lt(self, value):
        return self._trigger('lt', _number(value))

    def is_empty(self):
        return self._trigger('is_empty')

    def is_checked(self):
        return self._trigger('is_checked')

    # -- actions -------------------------------------------------------------
    def _action(self, kind, fields=(), **extra):
        action = {'action': kind}
        if fields:
            action['fields'] = _names(fields, allow_wildcard=kind in WILDCARD)
        action.update(extra)
        self.actions.append(action)
        return self

    def _targets(self, name, fields):
        if not fields:
            raise ValueError('%s() needs at least one field' % name)
        return self._action(name, fields)

    def show(self, *fields):
        return self._targets('show', fields)

    def hide(self, *fields):
        return self._targets('hide', fields)

    def enable(self, *fields):
        return self._targets('enable', fields)

    def disable(self, *fields):
        return self._targets('disable', fields)

    def require(self, *fields):
        return self._targets('require', fields)

    def refresh(self, *fields):
        return self._targets('refresh', fields)

    def add_class(self, css_class, *fields):
        return self._css('add_class', css_class, fields)

    def remove_class(self, css_class, *fields):
        return self._css('remove_class', css_class, fields)

    def _css(self, name, css_class, fields):
        if not isinstance(css_class, str) or not css_class.strip():
            raise TypeError('%s() needs a css class' % name)
        if not fields:
            raise ValueError('%s() needs at least one field' % name)
        return self._action(name, fields, css=css_class.strip())

    def set_value(self, field, value=_MISSING, *, from_field=None, server=None):
        """Give ``field`` a constant ``value``, the value of ``from_field`` or
        what the form method named ``server`` answers (it may set others)."""
        given = [value is not _MISSING, from_field is not None, server is not None]
        if sum(given) != 1:
            raise ValueError('set_value() takes one of value, from_field or server')
        _names([field])
        if from_field is not None:
            return self._action('set_value', [field], **{'from': _names(
                [from_field])[0]})
        if server is not None:
            if not isinstance(server, str) or not server.isidentifier() \
                    or server.startswith('_'):
                raise ValueError('server= is the name of a public form method')
            return self._action('set_value', [field], server=server)
        return self._action('set_value', [field], value=_json_value(value))

    def confirm(self, message):
        if not isinstance(message, (str, Promise)):
            raise TypeError('confirm() needs a message')
        return self._action('confirm', message=message)

    def call(self, name, *args):
        if not isinstance(name, str) or not name:
            raise TypeError('call() needs the name of a registered function')
        return self._action('call', name=name, args=[_json_value(a) for a in args])

    # -- serialization -------------------------------------------------------
    @property
    def server_methods(self):
        return [action['server'] for action in self.actions if 'server' in action]

    def serialize(self, form):
        """The rule as the runtime reads it, or None when it cannot fire.

        Field names are checked against the form: a name the form class does
        not know is a typo (ImproperlyConfigured); one the class knows but the
        instance removed (a field dropped in ``__init__``) is skipped.
        """
        if self.trigger is None:
            raise ImproperlyConfigured('%r has no trigger' % self)
        if not self.actions:
            raise ImproperlyConfigured('%r has no actions' % self)
        present = _field_resolver(form)
        sources = [name for name in self.fields if present(name)]
        if len(sources) != len(self.fields):
            return None
        actions = []
        for action in self.actions:
            action = dict(action)
            if 'fields' in action:
                fields = []
                for name in action['fields']:
                    if name == '*':
                        fields.extend(_wildcard(form, self.fields))
                    elif present(name):
                        fields.append(name)
                action['fields'] = list(dict.fromkeys(fields))
                if not action['fields']:
                    continue
            if 'from' in action and not present(action['from']):
                continue
            if 'server' in action:
                action['server'] = sign_method(type(form), action['server'],
                                               user=_form_user(form))
            if 'message' in action:
                action['message'] = str(action['message'])
            actions.append(action)
        if not actions:
            return None
        rule = {'when': sources, 'trigger': self.trigger, 'actions': actions}
        if self.trigger in ('equals', 'not_equals', 'in', 'gt', 'lt'):
            rule['value'] = self.value
        return rule


def _form_user(form):
    """The authenticated user of ``form.request``, if the form has one."""
    user = getattr(getattr(form, 'request', None), 'user', None)
    if user is not None and user.is_authenticated:
        return user
    return None


def _field_resolver(form):
    def present(name):
        if name in form.fields:
            return True
        if name in type(form).base_fields:
            return False
        raise ImproperlyConfigured(
            '%s.dynamic_actions names %r, which is not a field of the form'
            % (type(form).__name__, name))
    return present


def _wildcard(form, exclude):
    return [name for name, field in form.fields.items()
            if name not in exclude and not field.widget.is_hidden]


def form_path(form_class):
    if '<locals>' in form_class.__qualname__ or '.' in form_class.__qualname__:
        raise ImproperlyConfigured(
            '%s uses set_value(server=...) but is not a module level class, '
            'so the endpoint cannot import it' % form_class.__qualname__)
    return '%s.%s' % (form_class.__module__, form_class.__qualname__)


def server_methods(form_class):
    """The method names ``form_class`` declares in ``set_value(server=...)``."""
    names = set()
    for rule in getattr(form_class, 'dynamic_actions', None) or ():
        if isinstance(rule, When):
            names.update(rule.server_methods)
    return names


def token_max_age():
    return getattr(settings, 'GT_DYNAMIC_ACTIONS_MAX_AGE', DEFAULT_MAX_AGE)


def sign_method(form_class, method, user=None):
    """The token of ``form_class.method``; bound to ``user`` when given."""
    if method not in server_methods(form_class):
        # A rule added per instance, outside the class attribute: the endpoint
        # would refuse it, so refuse it here where the mistake is visible.
        raise ImproperlyConfigured(
            '%s: server method %r must be declared in the class attribute '
            'dynamic_actions' % (form_class.__name__, method))
    if not callable(getattr(form_class, method, None)):
        raise ImproperlyConfigured('%s has no method %r for set_value(server=...)'
                                   % (form_class.__name__, method))
    payload = {'form': form_path(form_class), 'method': method}
    if user is not None:
        payload['user'] = str(user.pk)
    # signing.dumps() stamps the time; load_token() checks it with max_age.
    return signing.dumps(payload, salt=SIGNING_SALT)


def load_token(token, max_age=_MISSING):
    """The payload ``{'form', 'method'[, 'user']}`` of a token.

    Raises ``signing.BadSignature`` (``SignatureExpired`` once it is older than
    ``GT_DYNAMIC_ACTIONS_MAX_AGE``) for a token that is not valid.
    """
    if max_age is _MISSING:
        max_age = token_max_age()
    payload = signing.loads(token, salt=SIGNING_SALT, max_age=max_age)
    if not isinstance(payload, dict) or not isinstance(payload.get('form'), str) \
            or not isinstance(payload.get('method'), str) \
            or not isinstance(payload.get('user', ''), str):
        raise signing.BadSignature('Malformed dynamic action token')
    return payload


def unsign_method(token, max_age=_MISSING):
    """``(form path, method)`` from a token, or ``signing.BadSignature``."""
    payload = load_token(token, max_age)
    return payload['form'], payload['method']


def serialize_rules(form, rules):
    serialized = []
    for rule in rules or ():
        if not isinstance(rule, When):
            raise ImproperlyConfigured('dynamic_actions holds When() rules, got %r'
                                       % (rule,))
        data = rule.serialize(form)
        if data is not None:
            serialized.append(data)
    return serialized


def dynamic_attrs(form, rules):
    """The ``data-gt-dynamic*`` attributes for ``rules``, as a dict."""
    serialized = serialize_rules(form, rules)
    if not serialized:
        return {}
    attrs = {
        'data-gt-dynamic': json.dumps(serialized, cls=DjangoJSONEncoder),
        'data-gt-dynamic-prefix': form.prefix or '',
        'data-gt-dynamic-fields': json.dumps(list(form.fields)),
    }
    if any('server' in action for rule in serialized for action in rule['actions']):
        try:
            attrs['data-gt-dynamic-url'] = reverse('gt-dynamic-action')
        except NoReverseMatch as error:
            raise ImproperlyConfigured(
                'set_value(server=...) needs djgentelella.urls in the URLconf'
            ) from error
    return attrs


def dynamic_marker(form, rules):
    """The hidden element that carries the rules, or '' when there are none."""
    attrs = dynamic_attrs(form, rules)
    if not attrs:
        return ''
    return format_html('<div class="gt-dynamic-actions" hidden{}></div>',
                       flatatt(attrs))
