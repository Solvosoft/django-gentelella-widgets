"""The registry of runtime components: one per node ``type``.

Filled, in this order, so a later ``type`` replaces an earlier one:

1. the built-in components (:mod:`djgentelella.designs.builtin`, then the
   components with data of :mod:`djgentelella.designs.data_components`,
   the interactive grid of :mod:`djgentelella.designs.grid`, the board of
   :mod:`djgentelella.designs.flow_kanban` and the cards, calendar and map
   of :mod:`djgentelella.designs.regions`, and the tree, timeline and metric
   cards of :mod:`djgentelella.designs.tree_timeline_metrics`);
2. the ``gtdesigns.py`` module of every installed app, imported from
   ``AppConfig.ready()`` -- it registers components with :func:`register` and
   exposes models with :func:`djgentelella.designs.exposure.expose`;
3. the dotted paths of the ``GT_DESIGN_COMPONENTS`` setting.

::

    # ventas/gtdesigns.py
    from djgentelella.designs.components import RuntimeComponent
    from djgentelella.designs.registry import register

    @register
    class Banner(RuntimeComponent):
        type = 'banner'
        ...
"""

import sys
import threading
from importlib import import_module, reload
from importlib.util import find_spec

from django.apps import apps
from django.utils.module_loading import import_string

from djgentelella.designs import (
    builtin, conf, data_components, flow_kanban, grid, regions,
    tree_timeline_metrics,
)

MODULE_NAME = 'gtdesigns'

_registered = {}
_state = {'loaded': False, 'loading': False, 'generation': 0}
#: Held while the registry loads, so another thread waits for it instead of
#: reading it half filled. Reentrant: loading registers components.
_lock = threading.RLock()

__all__ = ['autodiscover', 'generation', 'get_component', 'get_components',
           'register', 'reset']


def register(component_class):
    """Register a :class:`RuntimeComponent` subclass; usable as a decorator."""
    if not getattr(component_class, 'type', ''):
        raise ValueError('%s has no "type"' % component_class.__name__)
    with _lock:
        if not (_state['loaded'] or _state['loading']):
            # Registered by hand before the first use: the built-ins and the
            # gtdesigns modules come first, so this one wins over them.
            _load()
        _registered[component_class.type] = component_class()
        _state['generation'] += 1
    return component_class


def autodiscover(app_configs=None):
    """Import ``<app>.gtdesigns`` for every installed app that ships one.

    A module imported before is run again (after :func:`reset`), so it
    registers its components once more.
    """
    for config in apps.get_app_configs() if app_configs is None else app_configs:
        name = '%s.%s' % (config.name, MODULE_NAME)
        if name in sys.modules:
            reload(sys.modules[name])
        elif find_spec(name) is not None:
            import_module(name)


def _load():
    with _lock:
        if not _state['loaded']:
            _fill()


def _fill():
    _state['loading'] = True
    try:
        for component_class in (builtin.BUILTIN_COMPONENTS
                                + data_components.DATA_COMPONENTS
                                + grid.GRID_COMPONENTS
                                + flow_kanban.FLOW_KANBAN_COMPONENTS
                                + regions.REGION_COMPONENTS
                                + tree_timeline_metrics
                                .TREE_TIMELINE_METRICS_COMPONENTS):
            register(component_class)
        autodiscover()
        for path in conf.components():
            register(import_string(path))
        _state['loaded'] = True
    finally:
        _state['loading'] = False


def get_components():
    """``{type: RuntimeComponent instance}`` of every registered component."""
    if not _state['loaded']:
        _load()
    with _lock:
        return dict(_registered)


def get_component(node_type):
    return get_components().get(node_type)


def generation():
    """A number that changes whenever a component is registered.

    Part of the engine's cache key: a resolved page holds the components of
    the registry it was resolved with.
    """
    return _state['generation']


def reset():
    """Forget everything; the next :func:`get_components` loads again."""
    with _lock:
        _registered.clear()
        _state['loaded'] = False
        _state['generation'] += 1
