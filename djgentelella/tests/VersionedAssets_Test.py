"""Every stylesheet and script djgentelella links carries ``?v=<version>``:
after an upgrade a browser must not keep running the old file."""
import pathlib
import re

from django.test import SimpleTestCase
from django.test.utils import override_settings

import djgentelella
from djgentelella import __version__
from djgentelella.assets import versioned, versioned_static
from djgentelella.designs.engine import _asset_url

PACKAGE = pathlib.Path(djgentelella.__file__).parent
TAG = re.compile(r'<(script|link)\b[^>]*>', re.S | re.I)
URL = re.compile(r"""\b(?:src|href)\s*=\s*(["'])(.*?)\1""", re.S)
#: Links whose URL is not a static file: the media list of a design page
#: (already versioned by the engine) and the live preview of a theme.
NOT_STATIC = ('{{ url }}', '{{ preview_url }}')


@override_settings(STATIC_URL='/static/')
class VersionedAssetsTests(SimpleTestCase):
    def test_versioned(self):
        self.assertEqual(versioned('/a.js'), '/a.js?v=%s' % __version__)
        self.assertEqual(versioned('/a.js?x=1'), '/a.js?x=1&v=%s' % __version__)
        self.assertEqual(versioned(''), '')
        self.assertEqual(versioned_static('gentelella/js/a.js'),
                         '/static/gentelella/js/a.js?v=%s' % __version__)

    def test_every_template_link_has_the_version(self):
        missing = []
        for path in sorted(PACKAGE.rglob('*.html')):
            if 'tests' in path.parts:
                continue
            text = path.read_text(errors='ignore')
            for match in TAG.finditer(text):
                tag = match.group(0)
                if match.group(1).lower() == 'link' and 'stylesheet' not in tag:
                    continue
                url = URL.search(tag)
                if url is None or url.group(2).startswith(NOT_STATIC):
                    continue
                if 'get_version' not in url.group(2):
                    line = text[:match.start()].count('\n') + 1
                    missing.append('%s:%d %s' % (path.relative_to(PACKAGE), line,
                                                 url.group(2)))
        self.assertEqual(missing, [])

    def test_design_media_is_versioned(self):
        self.assertEqual(_asset_url('gentelella/js/designs/regions.js'),
                         '/static/gentelella/js/designs/regions.js?v=%s' % __version__)
        self.assertEqual(_asset_url('https://cdn.example/x.js'),
                         'https://cdn.example/x.js')
