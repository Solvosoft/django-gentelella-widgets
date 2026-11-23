"""The types a flow variable can be declared with.

A flow keeps its data in ``FlowInstance.variables``, a JSON object. Tools
that let people declare those variables -- a flow designer, an
automation editor -- offer a type for each one and check its default value
against it. This registry is the list they share, so none of them keeps its
own copy::

    from djgentelella.flows.variables import register_variable_type

    register_variable_type('money', (int, float, str), json_types=('number',
                           'string'), label='Money')

Each type says which Python values (as ``json.loads`` gives them) it takes.
``True`` and ``False`` are only ``boolean``: although ``bool`` is a subclass
of ``int`` in Python, a JSON boolean is not a number.
"""

from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _

__all__ = ['BUILTIN_TYPES', 'VariableType', 'check_variable', 'get_variable_type',
           'get_variable_types', 'register_variable_type',
           'unregister_variable_type']


@dataclass(frozen=True)
class VariableType:
    """One type of flow variable.

    ``python_types`` are the classes a value of it may be an instance of
    (after ``json.loads``) and ``json_types`` the JSON Schema ``type``\\ s of
    those values.
    """

    name: str
    python_types: tuple
    json_types: tuple
    label: str = ''

    def accepts(self, value):
        """Whether ``value`` is a valid value of this type."""
        if isinstance(value, bool) and bool not in self.python_types:
            return False
        return isinstance(value, self.python_types)

    def describe(self):
        """The type as plain JSON: ``{"name", "label", "json_types"}``."""
        return {'name': self.name, 'label': str(self.label or self.name),
                'json_types': list(self.json_types)}


_registry = {}


def register_variable_type(name, python_types, *, json_types, label=''):
    """Register (or replace) the variable type ``name``."""
    if not isinstance(name, str) or not name:
        raise ValueError('A variable type needs a name, not %r' % (name,))
    if isinstance(python_types, type):
        python_types = (python_types,)
    if isinstance(json_types, str):
        json_types = (json_types,)
    _registry[name] = VariableType(name, tuple(python_types), tuple(json_types),
                                   label)
    return _registry[name]


def unregister_variable_type(name):
    _registry.pop(name, None)


def get_variable_type(name):
    """The :class:`VariableType` called ``name``, or ``None``."""
    return _registry.get(name)


def get_variable_types():
    """``{name: VariableType}`` of every registered type, in the order they
    were registered."""
    return dict(_registry)


def check_variable(type_name, value):
    """Whether ``value`` is a valid value of the variable type ``type_name``;
    ``False`` for a type that is not registered."""
    found = _registry.get(type_name)
    return found is not None and found.accepts(value)


#: ``(name, python_types, json_types, label)`` of the types every project has.
BUILTIN_TYPES = (
    ('string', (str,), ('string',), _('Text')),
    ('integer', (int,), ('integer',), _('Integer')),
    # A decimal travels as a number or, to keep every digit, as text.
    ('decimal', (int, float, str), ('number', 'string'), _('Decimal')),
    ('boolean', (bool,), ('boolean',), _('Yes/No')),
    # Dates are ISO 8601 text: JSON has no date type.
    ('date', (str,), ('string',), _('Date')),
    ('datetime', (str,), ('string',), _('Date and time')),
    # A user by pk or by username.
    ('user', (int, str), ('integer', 'string'), _('User')),
    ('list', (list,), ('array',), _('List')),
    ('object', (dict,), ('object',), _('Object')),
)

for _name, _python_types, _json_types, _label in BUILTIN_TYPES:
    register_variable_type(_name, _python_types, json_types=_json_types,
                           label=_label)
