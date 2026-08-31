"""State contract and handlers of the PositionsGrid demo.

``PositionsGrid`` keeps no state of its own: every mutation leaves through a
handler that resolves with the new state, and the widget repaints with that.
So the handlers' answer *shape* is the widget's public contract, not a demo
detail -- if a rejected handler returned a partial state, the screen would show
something the server never confirmed.

The demo warehouse is the reference implementation of those seven handlers, and
these tests pin what it promises: the whole state every time, a 400 with a
``detail`` when the operation would destroy occupied cells, and above all a
**ragged shape that is never squared off**, because the shape is what the user
drew of their own wall.
"""

import ast
import inspect
import textwrap

from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from demoapp.models import Warehouse, WarehouseBox
from djgentelella.management.commands.createbasejs import Command

RAGGED = [2, 4, 3, 4]


class WarehouseHandlerTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.warehouse = Warehouse.objects.create(name='Wall', shape=list(RAGGED))
        self.box = WarehouseBox.objects.create(
            warehouse=self.warehouse, code='BOX-001', row=1, col=2)

    def url(self, handler):
        # DRF derives the url_name from the method name with dashes.
        return reverse(
            'api-warehouse-%s' % handler.replace('_', '-'),
            args=[self.warehouse.pk],
        )

    def call(self, handler, payload=None, method='post'):
        return getattr(self.client, method)(
            self.url(handler), payload or {}, format='json')

    def widths(self, response):
        return [len(row) for row in response.data['data']['cells']]

    # -- the state -------------------------------------------------------

    def test_the_state_is_cells_plus_items(self):
        response = self.call('state', method='get')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(sorted(response.data), ['data', 'items'])
        self.assertIn('cells', response.data['data'])
        # Items are keyed by string so the payload survives a JSON round trip.
        self.assertIn(str(self.box.pk), response.data['items'])

    def test_the_ragged_shape_survives_the_round_trip(self):
        self.assertEqual(self.widths(self.call('state', method='get')), RAGGED)

    def test_a_cell_can_hold_several_items(self):
        for code in ('BOX-002', 'BOX-003'):
            WarehouseBox.objects.create(
                warehouse=self.warehouse, code=code, row=1, col=2)
        cells = self.call('state', method='get').data['data']['cells']
        self.assertEqual(len(cells[1][2]), 3)

    def test_a_box_outside_the_shape_is_listed_but_not_placed(self):
        """It cannot vanish: the editor has to be able to see and move it."""
        stray = WarehouseBox.objects.create(
            warehouse=self.warehouse, code='BOX-OUT', row=9, col=9)
        response = self.call('state', method='get')
        self.assertIn(str(stray.pk), response.data['items'])
        placed = [
            pk for row in response.data['data']['cells'] for cell in row
            for pk in cell
        ]
        self.assertNotIn(stray.pk, placed)

    def test_every_handler_answers_the_whole_state(self):
        """What makes the seven interchangeable to the client."""
        calls = [
            ('add_row', {}),
            ('add_col', {}),
            ('create_item', {'row': 0, 'col': 0}),
            ('move_item', {'id': self.box.pk, 'row': 0, 'col': 1}),
            ('remove_item', {'id': self.box.pk}),
            # La fila y la columna sólo se pueden quitar vacías, y ese rechazo
            # tiene su propia prueba: aquí se mide la forma de la respuesta.
            ('empty', {}),
            ('remove_row', {'row': 0}),
            ('remove_col', {'col': 0}),
        ]
        for handler, payload in calls:
            if handler == 'empty':
                self.warehouse.boxes.all().delete()
                continue
            with self.subTest(handler=handler):
                response = self.call(handler, payload)
                self.assertEqual(response.status_code, status.HTTP_200_OK,
                                 response.data)
                self.assertEqual(sorted(response.data), ['data', 'items'])

    # -- growing ---------------------------------------------------------

    def test_add_row_is_as_wide_as_the_last_one(self):
        self.assertEqual(self.widths(self.call('add_row')), RAGGED + [4])

    def test_add_col_grows_every_row_by_one(self):
        self.assertEqual(self.widths(self.call('add_col')),
                         [width + 1 for width in RAGGED])

    # -- refusing --------------------------------------------------------

    def test_removing_a_row_with_boxes_is_refused_with_a_detail(self):
        response = self.call('remove_row', {'row': 1})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)
        self.warehouse.refresh_from_db()
        self.assertEqual(self.warehouse.shape, RAGGED)

    def test_removing_a_column_with_boxes_is_refused_with_a_detail(self):
        response = self.call('remove_col', {'col': 2})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)
        self.warehouse.refresh_from_db()
        self.assertEqual(self.warehouse.shape, RAGGED)

    def test_removing_something_that_is_not_there_is_refused(self):
        for handler, payload in (('remove_row', {'row': 9}),
                                 ('remove_col', {'col': 9})):
            with self.subTest(handler=handler):
                response = self.call(handler, payload)
                self.assertEqual(response.status_code,
                                 status.HTTP_400_BAD_REQUEST)

    def test_an_item_cannot_be_put_outside_the_shape(self):
        # Row 0 is two cells wide, so column 3 exists elsewhere but not here.
        for handler, payload in (
            ('create_item', {'row': 0, 'col': 3}),
            ('move_item', {'id': self.box.pk, 'row': 0, 'col': 3}),
        ):
            with self.subTest(handler=handler):
                response = self.call(handler, payload)
                self.assertEqual(response.status_code,
                                 status.HTTP_400_BAD_REQUEST)

    def test_an_item_of_another_warehouse_is_refused(self):
        other = Warehouse.objects.create(name='Other', shape=[2])
        stranger = WarehouseBox.objects.create(
            warehouse=other, code='BOX-X', row=0, col=0)
        response = self.call('move_item',
                             {'id': stranger.pk, 'row': 0, 'col': 0})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # -- renumbering, which is easy to break and hard to see -------------

    def test_removing_a_row_shifts_the_ones_below_up(self):
        self.box.delete()
        below = WarehouseBox.objects.create(
            warehouse=self.warehouse, code='BOX-B', row=2, col=0)
        self.call('remove_row', {'row': 0})
        below.refresh_from_db()
        self.assertEqual(below.row, 1)
        self.assertEqual(self.warehouse.__class__.objects.get(
            pk=self.warehouse.pk).shape, [4, 3, 4])

    def test_removing_a_column_shifts_the_ones_right_left(self):
        right = WarehouseBox.objects.create(
            warehouse=self.warehouse, code='BOX-R', row=1, col=3)
        self.box.delete()
        self.call('remove_col', {'col': 2})
        right.refresh_from_db()
        self.assertEqual(right.col, 2)

    def test_remove_col_only_shrinks_the_rows_that_have_it(self):
        """Row 0 has no column 3, so it is left exactly as the user drew it."""
        self.box.delete()
        response = self.call('remove_col', {'col': 3})
        self.assertEqual(self.widths(response), [2, 3, 3, 3])


class PositionsGridAssetsTestCase(TestCase):
    """The wiring: without it the widget loads but cannot draw."""

    def file_lists(self):
        """The two lists as the command actually declares them."""
        tree = ast.parse(textwrap.dedent(inspect.getsource(Command.handle)))
        found = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Name):
                continue
            if target.id in ('basefiles', 'jquery_plugins'):
                found[target.id] = [
                    element.value for element in node.value.elts
                    if isinstance(element, ast.Constant)
                ]
        return found

    def test_the_components_travel_with_the_classes(self):
        """A class declared inside ``(function($){...})(jQuery)`` is unreachable.

        ``jquery_plugins`` is emitted wrapped in that closure, so the two
        components have to travel in ``basefiles`` instead. Getting it wrong
        makes them vanish with no error other than ``PositionsGrid is not
        defined``, which is why this is worth a test and not a comment.
        """
        lists = self.file_lists()
        for component in ('positionsgrid.js', 'breadcrumbnav.js'):
            with self.subTest(component=component):
                self.assertIn(component, lists['basefiles'])
                self.assertNotIn(component, lists['jquery_plugins'])

    def test_the_stylesheets_are_linked_unconditionally(self):
        html = render_to_string(
            'gentelella/statics/stylesheets.html',
            request=RequestFactory().get('/'),
        )
        self.assertIn('positionsgrid.css', html)
        self.assertIn('breadcrumbnav.css', html)
