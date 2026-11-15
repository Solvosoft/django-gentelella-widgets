"""Which models a published design may use.

A design is data, written by whoever can publish one, so it cannot be allowed
to reach any model of the project: a form on ``auth.User`` would let it edit
passwords. Nothing is exposed by default. An app opts a model in from its
``gtdesigns.py``::

    from djgentelella.designs.exposure import expose
    from ventas.models import Cliente

    expose(Cliente, exclude=('notas_internas',))

or as a decorator, ``@expose`` or ``@expose(fields=[...])``.

``fields``/``exclude`` limit what a design can name (form fields, columns),
``perms`` what a user needs for each action on it -- by default the model's
own ``view``/``add``/``change``/``delete`` permissions.
"""

from dataclasses import dataclass, field

from django.apps import apps
from django.db import models

#: The actions an :class:`Exposure` knows default permissions for.
ACTIONS = ('view', 'add', 'change', 'delete')

_EXPOSED = {}
_state = {'generation': 0}


@dataclass
class Exposure:
    model: type
    fields: tuple = None
    exclude: tuple = ()
    perms: dict = field(default_factory=dict)

    @property
    def label(self):
        return self.model._meta.label

    def allows(self, name):
        """Whether a design may name the model field ``name``."""
        if self.fields is not None and name not in self.fields:
            return False
        return name not in self.exclude

    def model_fields(self):
        """The forward fields of the model a design may use, in model order."""
        opts = self.model._meta
        return [model_field for model_field in
                list(opts.fields) + list(opts.many_to_many)
                if self.allows(model_field.name)]

    def permissions(self, action):
        """``app.codename`` permissions a user needs to ``action`` the model."""
        if action in self.perms:
            return list(self.perms[action])
        opts = self.model._meta
        return ['%s.%s_%s' % (opts.app_label, action, opts.model_name)]


def _model(model):
    if isinstance(model, str):
        return apps.get_model(model)
    if isinstance(model, type) and issubclass(model, models.Model):
        return model
    raise TypeError('expose() takes a model class or an "app.Model" label, '
                    'not %r' % (model,))


def _perms(perms):
    if perms is None:
        return {}
    if isinstance(perms, dict):
        return {action: tuple(values) for action, values in perms.items()}
    # A plain list: the same permissions for every action.
    return {action: tuple(perms) for action in ACTIONS}


def expose(model=None, *, fields=None, exclude=(), perms=None):
    """Let published designs use ``model``. Exposing it again replaces it.

    Works as a call, ``expose(Model)``, and as a decorator, ``@expose`` or
    ``@expose(fields=...)``. Returns the model.
    """
    def register(target):
        target_model = _model(target)
        _EXPOSED[target_model._meta.label_lower] = Exposure(
            target_model, tuple(fields) if fields is not None else None,
            tuple(exclude), _perms(perms))
        _state['generation'] += 1
        return target

    if model is None:
        return register
    return register(model)


def unexpose(model):
    """Withdraw ``model``; mostly for tests."""
    _EXPOSED.pop(_model(model)._meta.label_lower, None)
    _state['generation'] += 1


def generation():
    """A number that changes whenever a model is exposed or withdrawn; part
    of the engine's cache key."""
    return _state['generation']


def exposed_models():
    """``{label: Exposure}`` of every exposed model."""
    return {exposure.label: exposure for exposure in _EXPOSED.values()}


def get_exposure(model):
    """The :class:`Exposure` of a model class or label, or ``None``."""
    if isinstance(model, str):
        return _EXPOSED.get(model.lower())
    return _EXPOSED.get(model._meta.label_lower)
