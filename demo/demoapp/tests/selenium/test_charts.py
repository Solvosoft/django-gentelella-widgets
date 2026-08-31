"""Browser test for ``DJGraph``, the Chart.js widget.

The widget fetches its whole configuration from a ``BaseChartGetter`` endpoint
and hands it to ``new Chart()`` untouched, so an option Chart.js no longer
understands produces no error anywhere in the markup -- just an empty canvas.
The page has to be opened and the pixels counted.
"""

from django.test import tag

from .base import SeleniumTestCase

#: /chartjs draws one of each: bar, horizontal bar, stacked, line, stepped,
#: area, pie, doughnut, mixed line+bar and scatter.
CHART_COUNT = 10


@tag('selenium')
class ChartWidgetTest(SeleniumTestCase):

    def open_charts(self):
        self.go('/chartjs')
        self.wait_js(
            "return typeof Chart !== 'undefined'", message='Chart.js never loaded')
        self.wait_js(
            "return Object.keys(Chart.instances || {}).length >= arguments[0]"
            " || document.querySelectorAll('.gentelella_graph canvas')"
            "    .length >= arguments[0]",
            CHART_COUNT, message='the canvases never appeared')

    def test_every_example_builds_a_chart(self):
        self.open_charts()

        self.assertEqual(
            self.js("return document.querySelectorAll("
                    "'[data-widget=DJGraph]').length"), CHART_COUNT)
        # jQuery.data('chartInstance') is what gentelella_chart stores after a
        # successful `new Chart(...)`; a rejected configuration never gets here.
        built = self.wait_js(
            "return Array.from(document.querySelectorAll('.gentelella_graph'))"
            "  .filter(e => jQuery(e).data('chartInstance')).length"
            "  === arguments[0] ? arguments[0] : false;",
            CHART_COUNT, message='not every chart was constructed')
        self.assertEqual(built, CHART_COUNT)

    def blank_canvases(self):
        """Ids of the chart canvases with no painted pixel at all."""
        return self.js(
            "const blank = [];"
            "for (const canvas of document.querySelectorAll("
            "        '.gentelella_graph canvas')) {"
            "  const ctx = canvas.getContext('2d');"
            "  const w = canvas.width, h = canvas.height;"
            "  if (!w || !h) { blank.push(canvas.id || 'unsized'); continue; }"
            "  const data = ctx.getImageData(0, 0, w, h).data;"
            "  let painted = false;"
            "  for (let i = 3; i < data.length; i += 4) {"
            "    if (data[i] !== 0) { painted = true; break; }"
            "  }"
            "  if (!painted) blank.push(canvas.id || 'blank');"
            "}"
            "return blank;")

    def test_the_charts_actually_paint(self):
        """A Chart.js configuration it cannot read leaves a blank canvas."""
        self.open_charts()

        # Polled, not asserted once: the ten charts animate in, so the last of
        # them is still empty for a few frames after the page settles.
        self.wait.until(lambda d: not self.blank_canvases(),
                        'some canvases never drew a single pixel')
        self.assertEqual(self.blank_canvases(), [])

    def test_the_options_reach_the_browser_in_the_v4_vocabulary(self):
        """The server sends title/legend/tooltip under ``options.plugins``."""
        self.open_charts()

        options = self.js(
            "return jQuery(document.querySelector('.gentelella_graph'))"
            "  .data('chartInstance').options;")
        self.assertIn('plugins', options)
        self.assertTrue(options['plugins']['title']['display'])

    def test_a_named_tooltip_callback_becomes_a_function(self):
        """The doughnut example asks for ``doughnutbeforeLabel`` by name; the
        widget swaps the string for the function in ``document.chartcallbacks``.
        """
        self.open_charts()

        kind = self.js(
            "for (const e of document.querySelectorAll('.gentelella_graph')) {"
            "  const chart = jQuery(e).data('chartInstance');"
            "  if (chart && chart.config.type === 'doughnut') {"
            "    return typeof chart.options.plugins.tooltip"
            "      .callbacks.beforeLabel;"
            "  }"
            "}"
            "return 'no doughnut';")
        self.assertEqual(kind, 'function')
