"""W21: Bootstrap is loaded as ``bootstrap.bundle.min.js``, with its own
Popper, in both branches of the page header -- the compressed bundle that
``pylpfile.py`` builds and the separate files. A separate ``popper.min.js``
left every dropdown dead (``createPopper is not a function``) wherever
``window.Popper`` was missing; the Selenium side is
``demoapp/tests/selenium/test_flow_kanban.py``."""

import re
from pathlib import Path
from unittest import skipUnless

from django.core.cache import cache
from django.template import Context, Template
from django.test import TestCase

import djgentelella
from djgentelella.models import GentelellaSettings

__all__ = ['BootstrapBundleTests']

PYLPFILE = Path(djgentelella.__file__).resolve().parent.parent / 'pylpfile.py'


class BootstrapBundleTests(TestCase):
    def header(self, compressed):
        GentelellaSettings.objects.update_or_create(
            key='use_compress_static', site=None,
            defaults={'value': 'true' if compressed else 'false'})
        cache.clear()
        self.addCleanup(cache.clear)
        return Template("{% include 'gentelella/statics/javascript_header.html' %}") \
            .render(Context({}))

    def test_the_separate_files_load_the_bundle(self):
        html = self.header(compressed=False)
        self.assertIn('vendors/bootstrap/bootstrap.bundle.min.js', html)
        self.assertNotIn('popper.min.js', html)
        self.assertNotIn('vendors/bootstrap/bootstrap.min.js', html)

    def test_the_compressed_header(self):
        html = self.header(compressed=True)
        self.assertIn('djgentelella.vendors.header.min.js', html)
        self.assertNotIn('vendors/bootstrap/', html)

    @skipUnless(PYLPFILE.exists(), 'pylpfile.py is not shipped in the package')
    def test_the_header_bundle_is_built_with_the_bundle(self):
        source = PYLPFILE.read_text()
        start = source.index('JS_FILES_HEADER =')
        block = source[start:source.index(']]', start)]
        files = [Path(path).name for path in re.findall(r"^\s*'([^']+)'", block, re.M)]
        self.assertIn('bootstrap.bundle.min.js', files)
        self.assertNotIn('popper.min.js', files)
        self.assertNotIn('bootstrap.min.js', files)
