"""``autodiscover_once``: the registries of authorizations, LOVs and data
sources import their ``<app>.<module>`` once, and no thread sees them half
filled while another one imports."""

import os
import subprocess
import sys
import threading
import time
from unittest import mock

from django.test import SimpleTestCase

import djgentelella
from djgentelella import autodiscover
from djgentelella.designs import registry


class AutodiscoverOnceTests(SimpleTestCase):
    def setUp(self):
        self.addCleanup(autodiscover._autodiscovered.discard, 'gttesting')

    def test_imports_once(self):
        with mock.patch.object(autodiscover, 'autodiscover_modules') as found:
            autodiscover.autodiscover_once('gttesting')
            autodiscover.autodiscover_once('gttesting')
        found.assert_called_once_with('gttesting')

    def test_a_failed_import_is_tried_again(self):
        with mock.patch.object(autodiscover, 'autodiscover_modules',
                               side_effect=[ImportError('boom'), None]) as found:
            with self.assertRaises(ImportError):
                autodiscover.autodiscover_once('gttesting')
            autodiscover.autodiscover_once('gttesting')
        self.assertEqual(found.call_count, 2)

    def test_another_thread_waits_for_the_imports(self):
        registered = []
        seen = []
        started = threading.Event()

        def slow_import(name):
            started.set()
            time.sleep(0.2)
            registered.append(name)

        def second():
            started.wait()
            autodiscover.autodiscover_once('gttesting')
            seen.append(list(registered))

        with mock.patch.object(autodiscover, 'autodiscover_modules',
                               side_effect=slow_import) as found:
            thread = threading.Thread(target=second)
            thread.start()
            autodiscover.autodiscover_once('gttesting')
            thread.join()
        found.assert_called_once_with('gttesting')
        # The second thread returned only once the registry was filled.
        self.assertEqual(seen, [['gttesting']])


class ImportBeforeAppsReadyTests(SimpleTestCase):
    def test_registries_import_before_the_app_registry_is_ready(self):
        # An AppConfig module of another app may import them at module level.
        code = ('import django.conf; django.conf.settings.INSTALLED_APPS; '
                'import djgentelella.datasources.export, djgentelella.lov')
        env = dict(os.environ)
        env.setdefault('DJANGO_SETTINGS_MODULE', 'demo.settings')
        # The child does not inherit the sys.path demo/manage.py builds: give
        # it the checkout root (djgentelella) and demo/ (demo.settings), or it
        # only works where djgentelella happens to be installed.
        root = os.path.dirname(os.path.dirname(os.path.abspath(djgentelella.__file__)))
        env['PYTHONPATH'] = os.pathsep.join(
            [root, os.path.join(root, 'demo')]
            + [path for path in [env.get('PYTHONPATH')] if path])
        result = subprocess.run([sys.executable, '-c', code], env=env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class DesignRegistryLoadTests(SimpleTestCase):
    def test_another_thread_waits_for_the_load(self):
        registry.reset()
        self.addCleanup(registry.reset)
        seen = []
        started = threading.Event()
        original = registry.autodiscover

        def slow_autodiscover(app_configs=None):
            started.set()
            time.sleep(0.2)
            original(app_configs)

        def second():
            started.wait()
            seen.append(len(registry.get_components()))

        with mock.patch.object(registry, 'autodiscover',
                               side_effect=slow_autodiscover) as discover:
            thread = threading.Thread(target=second)
            thread.start()
            total = len(registry.get_components())
            thread.join()
        # Loaded once, and the second thread got the whole registry.
        self.assertEqual(discover.call_count, 1)
        self.assertEqual(seen, [total])
