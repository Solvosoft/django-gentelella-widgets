"""Import a registry module of every installed app once per process.

Kept free of model imports: registries import it at module level, and they
may be imported from ``AppConfig`` modules before the app registry is ready.
"""
import threading

from django.utils.module_loading import autodiscover_modules

# Reentrant: importing one app's module may need another kind autodiscovered.
_autodiscover_lock = threading.RLock()
_autodiscovered = set()


def autodiscover_once(module_name):
    """Import ``<app>.<module_name>`` of every installed app that has one, the
    first time it is asked for in the process.

    Another thread asking meanwhile waits for the imports to finish instead
    of seeing a half-filled registry. The module counts as discovered only
    once every import worked: one that raised is tried again next time.
    """
    if module_name in _autodiscovered:
        return
    with _autodiscover_lock:
        if module_name not in _autodiscovered:
            autodiscover_modules(module_name)
            _autodiscovered.add(module_name)
