"""Shared helpers: process memory from /proc and per-module import attribution.

Linux only (reads /proc), stdlib only.
"""
import os
import sys
import time
import tracemalloc
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEMO = REPO / 'demo'
SCRIPTS = REPO / 'scripts'
OUT = Path(__file__).resolve().parent / 'out'

PROJECT_PREFIXES = ('djgentelella', 'demoapp', 'demo', 'memprofile')
_IMPORTLIB_NAMES = ('importlib', '_frozen_importlib', __name__)


def bootstrap(settings_module):
    """Make the child process look like ``cd demo && python manage.py``."""
    os.chdir(DEMO)
    for p in (str(SCRIPTS), str(REPO), str(DEMO)):
        if p not in sys.path:
            sys.path.insert(0, p)
    os.environ['DJANGO_SETTINGS_MODULE'] = settings_module


def _kb_field(path, field):
    try:
        with open(path) as fh:
            for line in fh:
                if line.startswith(field):
                    return int(line.split()[1])
    except OSError:
        pass
    return 0


def rss_kb():
    return _kb_field('/proc/self/status', 'VmRSS:')


def uss_kb():
    """Private (unshared) memory: what each extra worker really costs."""
    path = '/proc/self/smaps_rollup'
    return _kb_field(path, 'Private_Clean:') + _kb_field(path, 'Private_Dirty:')


def snapshot_process(label):
    mods = list(sys.modules)
    return {
        'phase': label,
        'rss_kb': rss_kb(),
        'uss_kb': uss_kb(),
        'modules': len(mods),
        'gt_modules': sum(1 for m in mods
                          if m == 'djgentelella' or m.startswith('djgentelella.')),
        'traced_kb': (tracemalloc.get_traced_memory()[0] // 1024
                      if tracemalloc.is_tracing() else None),
    }


def group_of(name):
    """Bucket for a project module: ``djgentelella.designs``, ``demoapp``..."""
    parts = name.split('.')
    if parts[0] == 'djgentelella':
        return '.'.join(parts[:2])
    return parts[0]


def is_project(name):
    return name.split('.')[0] in PROJECT_PREFIXES


def top_package(name):
    return name.split('.')[0]


def is_stdlib(name):
    top = top_package(name)
    return top in sys.stdlib_module_names or top.startswith('_')


class ImportProfiler:
    """Times and traces every source module's ``exec_module``.

    Memory and time are *exclusive*: nested imports are subtracted from the
    importer. Third-party modules are blamed on the nearest project frame of
    the Python call stack, so a function-level import inside djgentelella, or
    one run from ``AppConfig.ready()``, is blamed on the right code too.
    """

    def __init__(self):
        self.records = {}
        self._stack = []
        self._orig = None

    def install(self):
        import importlib._bootstrap_external as be  # noqa: PLC0415 -- private, only here
        self._be = be
        self._orig = be._LoaderBasics.exec_module
        profiler = self

        def exec_module(loader, module):
            return profiler._exec(loader, module)

        be._LoaderBasics.exec_module = exec_module

    def uninstall(self):
        if self._orig is not None:
            self._be._LoaderBasics.exec_module = self._orig
            self._orig = None

    @staticmethod
    def _blame(name):
        """(direct importer module, project group to blame)."""
        frame = sys._getframe(3)
        importer = None
        while frame is not None:
            fname = frame.f_globals.get('__name__', '')
            if fname != name and not fname.startswith(_IMPORTLIB_NAMES):
                importer = importer or fname
                if is_project(fname):
                    return importer, group_of(fname)
            frame = frame.f_back
        return importer, '(framework)'

    def _exec(self, loader, module):
        name = module.__name__
        frame = {'mem': 0, 'time': 0.0}
        importer, blame = self._blame(name)
        self._stack.append(frame)
        m0 = tracemalloc.get_traced_memory()[0]
        t0 = time.perf_counter()
        try:
            return self._orig(loader, module)
        finally:
            incl_mem = tracemalloc.get_traced_memory()[0] - m0
            incl_time = time.perf_counter() - t0
            self._stack.pop()
            if self._stack:
                self._stack[-1]['mem'] += incl_mem
                self._stack[-1]['time'] += incl_time
            self.records[name] = {
                'self_bytes': incl_mem - frame['mem'],
                'self_ms': round((incl_time - frame['time']) * 1000, 3),
                'incl_bytes': incl_mem,
                'group': group_of(name) if is_project(name) else blame,
                'importer': importer,
                'own': is_project(name),
                'stdlib': is_stdlib(name),
            }


def write_json(path, data):
    import json  # noqa: PLC0415 -- keep json out of the measured startup
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, sort_keys=True))
