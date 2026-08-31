"""The server-rendered seed that ``BreadcrumbNav`` takes over.

The widget exists because a path has to change without a request: the labview
map moves from room to furniture to shelf and the breadcrumb has to follow. But
the first paint is server side, so the trail is on screen before javascript
runs and does not flash in.

That makes ``blocks/breadcrumb.html`` a contract in two directions: it renders
the semantic markup Bootstrap expects, and it carries the ``data-bn-index``
hooks the widget takes the node over by. Its most important promise, though, is
the one about everything else: **with no ``breadcrumbs`` in the context it
renders nothing at all**, which is what let it be wired into the previously
empty block of ``base.html`` and ``plain.html`` without changing a single
existing page.
"""

from django.template.loader import get_template, render_to_string
from django.test import TestCase

LEVELS = [
    {'label': 'Demo', 'href': '/'},
    {'label': 'Warehouse', 'href': '/warehouse'},
    {'label': 'Wall A'},
]


class BreadcrumbBlockTestCase(TestCase):

    def render(self, context=None):
        return render_to_string(
            'gentelella/blocks/breadcrumb.html', context or {})

    def test_without_breadcrumbs_it_renders_nothing(self):
        """The compatibility promise: no context, no output, no page changed."""
        self.assertEqual(self.render().strip(), '')
        self.assertEqual(self.render({'breadcrumbs': []}).strip(), '')

    def test_it_renders_one_item_per_level(self):
        html = self.render({'breadcrumbs': LEVELS})
        self.assertEqual(html.count('breadcrumb-item'), len(LEVELS))
        for level in LEVELS:
            self.assertIn(level['label'], html)

    def test_the_last_level_is_the_current_page_and_not_a_link(self):
        html = self.render({'breadcrumbs': LEVELS})
        self.assertIn('aria-current="page"', html)
        self.assertIn('breadcrumb-item active', html)
        # El último trae href y aun así no se pinta como enlace.
        self.assertNotIn('<a href="/warehouse"', html.rsplit('Wall A', 1)[1])

    def test_intermediate_levels_with_href_are_links(self):
        html = self.render({'breadcrumbs': LEVELS})
        self.assertIn('href="/"', html)
        self.assertIn('href="/warehouse"', html)

    def test_a_level_without_href_is_not_a_link(self):
        html = self.render({'breadcrumbs': [{'label': 'Solo'}]})
        self.assertNotIn('<a ', html)
        self.assertIn('Solo', html)

    def test_data_bn_index_is_the_zero_based_position(self):
        """The hook the widget uses to take each node over."""
        html = self.render({'breadcrumbs': LEVELS})
        for index in range(len(LEVELS)):
            self.assertIn('data-bn-index="%d"' % index, html)

    def test_the_node_id_can_be_overridden(self):
        default = self.render({'breadcrumbs': LEVELS})
        self.assertIn('id="gt-breadcrumb"', default)

        custom = self.render(
            {'breadcrumbs': LEVELS, 'breadcrumbs_id': 'map-trail'})
        self.assertIn('id="map-trail"', custom)
        self.assertNotIn('id="gt-breadcrumb"', custom)

    def test_it_is_navigation_for_a_screen_reader(self):
        html = self.render({'breadcrumbs': LEVELS})
        self.assertIn('<nav', html)
        self.assertIn('aria-label=', html)


class BreadcrumbWiringTestCase(TestCase):
    """The block was empty in both bases; now it has a seed and still may be."""

    def test_both_bases_include_the_block(self):
        for template in ('gentelella/base.html', 'gentelella/plain.html'):
            with self.subTest(template=template):
                with open(_template_path(template), encoding='utf-8') as handle:
                    source = handle.read()
                self.assertIn('{% block breadcrumbs %}', source)
                self.assertIn(
                    "{% include 'gentelella/blocks/breadcrumb.html' %}", source)


def _template_path(name):
    return get_template(name).origin.name
