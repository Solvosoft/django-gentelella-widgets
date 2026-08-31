PositionsGrid
^^^^^^^^^^^^^^^^^

A matrix of rows and cells where each cell holds zero or more **opaque items**.
The widget knows nothing about what an item is: the host decides how it looks
with ``renderItem`` and what each gesture does with ``handlers``.

.. code:: javascript

   const grid = new PositionsGrid('warehouseGrid', {
       editable: true,
       renderItem: (item) => `<div class="card card-body p-2">${item.code}</div>`,
       handlers: {
           addRow:     ()         => post('add_row'),
           removeRow:  (i)        => post('remove_row', {row: i}),
           addCol:     ()         => post('add_col'),
           removeCol:  (i)        => post('remove_col', {col: i}),
           createItem: (r, c)     => post('create_item', {row: r, col: c}),
           moveItem:   (id, r, c) => post('move_item', {id: id, row: r, col: c}),
           removeItem: (id)       => post('remove_item', {id: id})
       }
   });

The state contract
""""""""""""""""""

This is the part that matters. **The widget keeps no state of its own.** ``data``
and ``items`` are always the last payload a handler resolved with. Every
mutation goes out through a handler that returns ``Promise<{data, items}>``, and
the only thing the widget does with the answer is repaint.

A **rejected** promise repaints nothing and fires ``pg:error``. The screen keeps
showing exactly what the server last confirmed, so a failed request cannot leave
the grid displaying something the server never agreed to. Nothing is applied
optimistically, and there is no *Save* button because there is no intermediate
state to lose.

Only one mutation is in flight at a time; a second call while the first is
pending fires ``pg:error`` with ``code: 'busy'`` and does nothing.

Irregular rows
""""""""""""""

Rows may have different lengths, and that is the point: the shape is the host's
data, not a grid the widget imposes. A warehouse of ``[2, 4, 3, 4]`` renders as

.. code::

   row 1  | A | B |
   row 2  | A | B | C | D |
   row 3  | A | B | C |
   row 4  | A | B | C | D |

Every cell is the same width and the rows are left aligned, so a two-cell row
occupies exactly half the width of a four-cell one. Nothing is padded out to a
rectangle. Internally each row is its own CSS grid and they all share one track
template driven by ``--pg-cols`` (the longest row), which is what keeps the
columns lined up without inventing filler cells.

Options
"""""""

============================ ==================================================
``data``                     ``{cells: [[[id, ...], ...], ...]}``
``items``                    ``{id: {...}}``, the catalogue the ids point at
``renderItem``               ``(item, id) -> html``; host HTML, not escaped
``renderEmptyCell``          ``(row, col) -> html`` for an empty cell
``editable``                 shows the editing controls (default ``false``)
``cellMinWidth``             narrowest a cell gets before sideways scroll
``drag``                     ``null`` = only where there is a fine pointer
``handlers``                 the seven functions below
``labels``                   overrides for the accessible names
============================ ==================================================

Handlers
""""""""

Every handler resolves with the **whole** new state, so from the widget's point
of view they are interchangeable. A missing handler means the control does not
exist: that is how partial permissions compose without a flag per action.

============================= =================================================
``addRow()``                  a new row
``removeRow(index)``          reject when the row still holds items
``addCol()``                  one cell to **every** row, so irregularity stays
``removeCol(index)``          only the rows that have that column shrink
``createItem(row, col)``      the host opens its own form
``moveItem(id, row, col)``    always by id, never by DOM coordinates
``removeItem(id)``
============================= =================================================

Methods
"""""""

``setData(data, items)``, ``setEditable(editable)``, ``highlight(id)``,
``scrollToItem(id)``, ``select(id)``, ``clearSelection()``, ``destroy()``, plus
the seven mutators, which are the public form of the handlers.

Events
""""""

All bubble, none are cancelable — cancelling would mean local state divergence,
which is the thing this widget refuses to have.

============================ ==================================================
``pg:item-click``            ``{grid, id, item, row, col, originalEvent}``
``pg:cell-click``            ``{grid, row, col, ids, originalEvent}``
``pg:selection-change``      ``{grid, id}``, ``id === null`` when cleared
``pg:before-change``         ``{grid, action, args}``
``pg:changed``               ``{grid, action, args, state}``
``pg:error``                 ``{grid, action, args, error, code}``
============================ ==================================================

Keyboard and touch
""""""""""""""""""

Moving an item is **two taps**: tap the item to pick it, tap a cell to place it.
No drag API is involved, so it works identically on a phone and from the
keyboard; the desktop drag reuses the same code path and is only enabled where
there is a fine pointer.

Arrow keys move between cells with a roving ``tabindex``, and the clamp respects
the irregularity: going down from column 3 into a two-cell row lands on that
row's last cell rather than nowhere. ``Enter`` picks and places, ``Escape``
cancels, ``Delete`` removes when editing.

.. note::
   ``base.js`` is generated. After changing the widget run
   ``python manage.py createbasejs``.

The demo at ``/positionsgrid_view`` wires all seven handlers to real endpoints
and refuses to delete a row that still holds boxes, which is the only way to see
the rejection path on screen.
