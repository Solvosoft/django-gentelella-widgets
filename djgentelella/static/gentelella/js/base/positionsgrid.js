/* Generic positions grid: rows x cells, each cell holding 0..N opaque items.
 *
 * The widget owns no state of its own. `data` and `items` are always the last
 * payload a handler resolved with; every mutation goes out through a handler
 * that returns Promise<{data, items}>, and the only thing the widget does with
 * the answer is repaint. A rejected promise repaints nothing, so a failed
 * request can never leave the screen showing something the server did not
 * agree to. Everything below is layout, accessibility and the promise gate
 * that enforces that.
 *
 * Rows are irregular on purpose: a row of two cells is half the width of a row
 * of four, cells stay left aligned and nothing is padded out to a rectangle.
 * The shape is the host's data, not a grid the widget imposes.
 *
 * A class, like CardList in api_list.js: a host-instantiated component with
 * public methods and a lifecycle. The ObjectCRUD factory in
 * obj_api_management.js predates classes and threads `instance` through every
 * method by hand; nothing here needs that.
 *
 * createbasejs concatenates this into base.js from `basefiles`, never from
 * `jquery_plugins` -- that block is wrapped in (function($){...})(jQuery) and a
 * class declared inside it would not be reachable. A class declaration is also
 * not hoisted the way a function declaration is, so nothing else in base.js may
 * touch PositionsGrid at load time; pages instantiate it on ready.
 */

var PG_DEFAULTS = {
    data: {cells: []},
    items: {},
    editable: false,
    renderItem: null,        // (item, id) -> html string
    renderEmptyCell: null,   // (row, col) -> html string
    cellMinWidth: '9rem',    // narrowest a cell gets before sideways scroll
    drag: null,              // null = auto: only where there is a fine pointer
    handlers: {},            // addRow removeRow addCol removeCol
                             // createItem moveItem removeItem
    labels: {}
};

function pg_escape(value) {
    return String(value === null || value === undefined ? '' : value)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function pg_gettext(text) {
    return (typeof gettext === 'function') ? gettext(text) : text;
}

function pg_format(template, values) {
    return String(template).replace(/%\((\w+)\)s/g, function (match, key) {
        return (key in values) ? values[key] : match;
    });
}

class PositionsGrid {

    constructor(el, options) {
        this.el = (typeof el === 'string') ? document.getElementById(el) : el;
        if (!this.el) throw new Error('PositionsGrid: container not found');
        var cfg = Object.assign({}, PG_DEFAULTS, options || {});
        cfg.labels = Object.assign({
            grid: pg_gettext('Positions'),
            addRow: pg_gettext('Add row'),
            removeRow: pg_gettext('Remove row %(n)s'),
            addCol: pg_gettext('Add column'),
            removeCol: pg_gettext('Remove column %(n)s'),
            createItem: pg_gettext('Add item here'),
            cell: pg_gettext('Row %(row)s, column %(col)s, %(count)s items'),
            picked: pg_gettext('Item selected. Choose a destination cell.'),
            cancelled: pg_gettext('Move cancelled.')
        }, (options || {}).labels);
        this.cfg = cfg;
        this.handlers = cfg.handlers || {};
        this.data = cfg.data || {cells: []};
        this.items = cfg.items || {};
        this.editable = !!cfg.editable;
        this.selectedId = null;   // transient UI state, never serialised
        this.busy = false;
        // data-* attributes stringify everything. Ids are opaque and may be
        // numbers, so this maps the string back and handlers get the id the
        // server sent, not "12".
        this._ids = {};
        this._active = {row: 0, col: 0};   // roving tabindex position
        this._buildChrome();
        this.render();
    }

    /* ------------------------------------------------------------------ *
     * chrome                                                              *
     * ------------------------------------------------------------------ */

    // Built once. Every listener is delegated on the container, so a repaint
    // (which replaces all the inner HTML) never leaves a dangling handler and
    // never needs re-binding.
    _buildChrome() {
        this.el.classList.add('pg');
        this.el.innerHTML =
            '<div class="pg-toolbar"></div>' +
            '<div class="pg-scroll"><div class="pg-rows" role="grid"></div></div>' +
            '<div class="pg-live visually-hidden" aria-live="polite"></div>';
        this.toolbar = this.el.querySelector('.pg-toolbar');
        this.scroll = this.el.querySelector('.pg-scroll');
        this.rowsEl = this.el.querySelector('.pg-rows');
        this.live = this.el.querySelector('.pg-live');
        this.rowsEl.setAttribute('aria-label', this.cfg.labels.grid);
        this._onClick = this._handleClick.bind(this);
        this._onKeydown = this._handleKeydown.bind(this);
        this.el.addEventListener('click', this._onClick);
        this.el.addEventListener('keydown', this._onKeydown);
        this._bindDrag();
    }

    /* ------------------------------------------------------------------ *
     * rendering                                                           *
     * ------------------------------------------------------------------ */

    render() {
        var rows = (this.data && this.data.cells) || [];
        // Irregular by design: the number of tracks is the LONGEST row, and a
        // shorter row simply leaves its trailing tracks empty. No padding to a
        // rectangle, cells left aligned, identical width in every row.
        var cols = rows.reduce(function (m, r) { return Math.max(m, r.length); }, 0);
        this._maxCols = cols;
        this.rowsEl.style.setProperty('--pg-cols', String(Math.max(cols, 1)));
        this.el.style.setProperty('--pg-cell-min', this.cfg.cellMinWidth);
        this.rowsEl.setAttribute('aria-rowcount', String(rows.length + 1));
        this.rowsEl.setAttribute('aria-colcount', String(Math.max(cols, 1)));
        this.el.classList.toggle('pg-editable', this.editable);

        var focus = this._captureFocus();
        var scrollLeft = this.scroll.scrollLeft;
        this._ids = {};

        this.toolbar.innerHTML = this._renderToolbar();
        this.rowsEl.innerHTML = this._renderHead(cols) +
            rows.map(this._renderRow, this).join('');

        // Items are host HTML and may carry library widgets or friconix icons,
        // exactly like a card in api_list.js. friconix scans once on load and
        // has no MutationObserver, hence the explicit refresh.
        if (typeof gt_find_initialize_from_dom === 'function') {
            gt_find_initialize_from_dom(this.rowsEl);
        }
        if (typeof gt_friconix_refresh === 'function') { gt_friconix_refresh(); }

        this._applySelection();
        this.scroll.scrollLeft = scrollLeft;
        this._restoreFocus(focus);
    }

    _renderToolbar() {
        var out = '';
        if (this.editable && this.handlers.addRow) {
            out += this._btn('add-row', {}, 'fa fa-plus', this.cfg.labels.addRow,
                             'btn btn-sm btn-outline-primary');
        }
        if (this.editable && this.handlers.addCol) {
            out += this._btn('add-col', {}, 'fa fa-plus', this.cfg.labels.addCol,
                             'btn btn-sm btn-outline-primary');
        }
        return out;
    }

    // The header row exists only to hold the per-column remove buttons, so it
    // is not rendered at all when the host gave no removeCol handler. Same rule
    // everywhere: a missing handler means the control does not exist, which is
    // how partial permissions compose without a flag per action.
    _renderHead(cols) {
        if (!this.editable || !this.handlers.removeCol || !cols) { return ''; }
        var cells = '';
        for (var c = 0; c < cols; c++) {
            cells += '<div class="pg-head-cell">' +
                this._btn('remove-col', {col: c}, 'fa fa-minus',
                          pg_format(this.cfg.labels.removeCol, {n: c + 1})) +
                '</div>';
        }
        return '<div class="pg-row pg-head" role="row" aria-hidden="true">' +
               '<div class="pg-gutter"></div>' + cells + '</div>';
    }

    _renderRow(cells, r) {
        var canRemove = this.editable && this.handlers.removeRow;
        return '<div class="pg-row" role="row" aria-rowindex="' + (r + 2) + '">' +
            '<div class="pg-gutter" role="rowheader">' +
                '<span class="pg-rownum">' + (r + 1) + '</span>' +
                (canRemove ? this._btn('remove-row', {row: r}, 'fa fa-minus',
                     pg_format(this.cfg.labels.removeRow, {n: r + 1})) : '') +
            '</div>' +
            cells.map(function (ids, c) {
                return this._renderCell(r, c, ids);
            }, this).join('') +
        '</div>';
    }

    _renderCell(r, c, ids) {
        var label = pg_format(this.cfg.labels.cell,
                              {row: r + 1, col: c + 1, count: ids.length});
        var body = ids.length
            ? ids.map(this._renderItem, this).join('')
            : (this.cfg.renderEmptyCell ? this.cfg.renderEmptyCell(r, c) : '');
        var add = (this.editable && this.handlers.createItem)
            ? this._btn('create-item', {row: r, col: c}, 'fa fa-plus',
                        this.cfg.labels.createItem, 'pg-cell-add')
            : '';
        return '<div class="pg-cell" role="gridcell" tabindex="-1"' +
               ' data-pg-row="' + r + '" data-pg-col="' + c + '"' +
               ' aria-colindex="' + (c + 1) + '"' +
               ' aria-label="' + pg_escape(label) + '">' +
               '<div class="pg-cell-items">' + body + '</div>' + add +
               '</div>';
    }

    _renderItem(id) {
        var item = this.items[id];
        if (item === undefined) { return ''; }   // unknown id: server truth wins
        this._ids[String(id)] = id;
        var draggable = this.dragEnabled && this.editable && this.handlers.moveItem;
        // The body is host HTML on purpose and is NOT escaped: renderItem is
        // the host's decision about appearance. Everything the widget puts
        // around it is escaped.
        var body = this.cfg.renderItem
            ? this.cfg.renderItem(item, id)
            : '<span class="pg-item-default">' +
              pg_escape(item.label !== undefined ? item.label : id) + '</span>';
        return '<div class="pg-item" role="button" tabindex="-1" aria-pressed="false"' +
               (draggable ? ' draggable="true"' : '') +
               ' data-pg-item="' + pg_escape(id) + '">' + body + '</div>';
    }

    _btn(action, args, icon, label, cls) {
        var data = '';
        for (var key in args) {
            if (Object.prototype.hasOwnProperty.call(args, key)) {
                data += ' data-pg-' + key + '="' + pg_escape(args[key]) + '"';
            }
        }
        return '<button type="button" data-pg-action="' + action + '"' + data +
               ' class="' + (cls || 'btn btn-sm btn-link') + '"' +
               ' title="' + pg_escape(label) + '"' +
               ' aria-label="' + pg_escape(label) + '">' +
               '<i class="' + icon + '" aria-hidden="true"></i></button>';
    }

    /* ------------------------------------------------------------------ *
     * the promise gate                                                    *
     * ------------------------------------------------------------------ */

    // The single place a handler is ever called, and the single place `data`
    // and `items` are ever assigned.
    _run(action, args, invoke) {
        if (this.busy) {
            this._emit('pg:error', {action: action, args: args, code: 'busy'});
            return Promise.resolve(false);
        }
        this.busy = true;
        this.el.classList.add('pg-busy');
        this.el.setAttribute('aria-busy', 'true');
        this._emit('pg:before-change', {action: action, args: args});
        var promise;
        try { promise = invoke(); } catch (error) { promise = Promise.reject(error); }
        var self = this;
        return Promise.resolve(promise).then(function (state) {
            self._settle();
            if (state) { self.setData(state.data, state.items); }
            self._emit('pg:changed', {action: action, args: args, state: state});
            return true;
        }, function (error) {
            self._settle();
            // Deliberately repaints nothing: the grid keeps showing the last
            // state the server confirmed.
            self._emit('pg:error', {action: action, args: args,
                                    error: error, code: 'handler'});
            return false;
        });
    }

    _settle() {
        this.busy = false;
        this.el.classList.remove('pg-busy');
        this.el.removeAttribute('aria-busy');
    }

    _call(name, args) {
        var fn = this.handlers[name];
        if (typeof fn !== 'function') { return Promise.resolve(false); }
        var self = this;
        return this._run(name, args, function () { return fn.apply(self, args); });
    }

    /* ------------------------------------------------------------------ *
     * public mutators                                                     *
     * ------------------------------------------------------------------ */

    addRow() { return this._call('addRow', []); }
    removeRow(index) { return this._call('removeRow', [index]); }
    addCol() { return this._call('addCol', []); }
    removeCol(index) { return this._call('removeCol', [index]); }
    createItem(row, col) { return this._call('createItem', [row, col]); }
    moveItem(id, row, col) { return this._call('moveItem', [id, row, col]); }
    removeItem(id) { return this._call('removeItem', [id]); }

    /* ------------------------------------------------------------------ *
     * public API                                                          *
     * ------------------------------------------------------------------ */

    setData(data, items) {
        if (data) { this.data = data; }
        if (items) { this.items = items; }
        // An item that vanished from the payload cannot stay selected.
        if (this.selectedId !== null && !(this.selectedId in this.items)) {
            this.selectedId = null;
        }
        this.render();
    }

    setEditable(editable) { this.editable = !!editable; this.render(); }

    highlight(id) {
        var previous = this.rowsEl.querySelector('.pg-highlight');
        if (previous) { previous.classList.remove('pg-highlight'); }
        var node = this._itemNode(id);
        if (node) { node.classList.add('pg-highlight'); }
        return !!node;
    }

    // scrollIntoView() would also scroll the page and every ancestor scroller;
    // the requirement is that only this widget scrolls, so the offsets are
    // applied to .pg-scroll by hand.
    scrollToItem(id) {
        var node = this._itemNode(id);
        if (!node) { return false; }
        var n = node.getBoundingClientRect(), s = this.scroll.getBoundingClientRect();
        this.scroll.scrollLeft += (n.left - s.left) - (s.width - n.width) / 2;
        return true;
    }

    select(id) {
        this.selectedId = id;
        this._applySelection();
        this._announce(this.cfg.labels.picked);
        this._emit('pg:selection-change', {id: id});
    }

    clearSelection() {
        if (this.selectedId === null) { return; }
        this.selectedId = null;
        this._applySelection();
        this._announce(this.cfg.labels.cancelled);
        this._emit('pg:selection-change', {id: null});
    }

    destroy() {
        this.el.removeEventListener('click', this._onClick);
        this.el.removeEventListener('keydown', this._onKeydown);
        this._unbindDrag();
        this.el.innerHTML = '';
        this.el.classList.remove('pg', 'pg-editable', 'pg-busy');
    }

    /* ------------------------------------------------------------------ *
     * interaction                                                         *
     * ------------------------------------------------------------------ */

    _handleClick(event) {
        var btn = event.target.closest('[data-pg-action]');
        if (btn && this.el.contains(btn)) {
            event.preventDefault();
            return this._dispatchAction(btn);
        }
        var itemEl = event.target.closest('.pg-item');
        if (itemEl && this.el.contains(itemEl)) {
            var id = this._ids[itemEl.dataset.pgItem];
            var at = this._locate(id) || {};
            this._emit('pg:item-click', {id: id, item: this.items[id],
                                         row: at.row, col: at.col,
                                         originalEvent: event});
            if (this.editable && this.handlers.moveItem) {
                if (this.selectedId === id) { this.clearSelection(); }
                else { this.select(id); }
            }
            return;
        }
        var cellEl = event.target.closest('.pg-cell');
        if (cellEl && this.el.contains(cellEl)) {
            var row = parseInt(cellEl.dataset.pgRow, 10);
            var col = parseInt(cellEl.dataset.pgCol, 10);
            this._active = {row: row, col: col};
            this._emit('pg:cell-click', {row: row, col: col,
                                         ids: (this.data.cells[row][col] || []).slice(),
                                         originalEvent: event});
            // Move by touch: tap the item, then tap the destination. No drag
            // API involved, so it works identically on a phone and from the
            // keyboard.
            if (this.selectedId !== null) { this._placeInto(row, col); }
        }
    }

    _dispatchAction(btn) {
        var action = btn.dataset.pgAction;
        if (action === 'add-row') { return this.addRow(); }
        if (action === 'add-col') { return this.addCol(); }
        if (action === 'remove-row') {
            return this.removeRow(parseInt(btn.dataset.pgRow, 10));
        }
        if (action === 'remove-col') {
            return this.removeCol(parseInt(btn.dataset.pgCol, 10));
        }
        if (action === 'create-item') {
            return this.createItem(parseInt(btn.dataset.pgRow, 10),
                                   parseInt(btn.dataset.pgCol, 10));
        }
    }

    _placeInto(row, col) {
        var id = this.selectedId, at = this._locate(id);
        this.clearSelection();
        // Dropping onto the cell it already occupies is a no-op, not a round
        // trip that would come back with an identical state.
        if (!at || (at.row === row && at.col === col)) { return; }
        this.moveItem(id, row, col);
    }

    // Roving tabindex: exactly one cell is in the tab order, arrows move
    // between cells, and the clamp respects the irregularity -- going down
    // from column 3 into a two-cell row lands on that row's last cell rather
    // than nowhere.
    _handleKeydown(event) {
        var cells = (this.data && this.data.cells) || [];
        if (!cells.length) { return; }
        var cellEl = event.target.closest('.pg-cell');
        var itemEl = event.target.closest('.pg-item');
        if (!cellEl && !itemEl) { return; }

        var pos = cellEl
            ? {row: parseInt(cellEl.dataset.pgRow, 10),
               col: parseInt(cellEl.dataset.pgCol, 10)}
            : this._locate(this._ids[itemEl.dataset.pgItem]);
        if (!pos) { return; }

        var row = pos.row, col = pos.col, handled = true;
        switch (event.key) {
        case 'ArrowRight': col += 1; break;
        case 'ArrowLeft': col -= 1; break;
        case 'ArrowDown': row += 1; break;
        case 'ArrowUp': row -= 1; break;
        case 'Home': col = event.ctrlKey ? (row = 0, 0) : 0; break;
        case 'End':
            if (event.ctrlKey) { row = cells.length - 1; }
            col = cells[Math.max(0, Math.min(row, cells.length - 1))].length - 1;
            break;
        case 'Escape': this.clearSelection(); return;
        case 'Delete':
        case 'Backspace':
            if (this.editable && itemEl && this.handlers.removeItem) {
                event.preventDefault();
                this.removeItem(this._ids[itemEl.dataset.pgItem]);
            }
            return;
        case 'Enter':
        case ' ':
            event.preventDefault();
            if (itemEl) {
                var id = this._ids[itemEl.dataset.pgItem];
                if (this.editable && this.handlers.moveItem) {
                    if (this.selectedId === id) { this.clearSelection(); }
                    else { this.select(id); }
                }
                this._emit('pg:item-click', {id: id, item: this.items[id],
                                             row: row, col: col,
                                             originalEvent: event});
            } else if (this.selectedId !== null) {
                this._placeInto(row, col);
            } else {
                var first = cellEl.querySelector('.pg-item');
                if (first) { first.focus(); }
            }
            return;
        default: handled = false;
        }
        if (!handled) { return; }
        event.preventDefault();
        row = Math.max(0, Math.min(row, cells.length - 1));
        col = Math.max(0, Math.min(col, cells[row].length - 1));
        this._active = {row: row, col: col};
        this._focusCell(row, col);
    }

    // Optional and cheap: it reuses _placeInto, so drag and tap-tap are the
    // same code path. Gated on a fine pointer so a touch device never gets the
    // HTML5 drag behaviour, which is unusable there.
    _bindDrag() {
        var auto = window.matchMedia &&
                   window.matchMedia('(hover: hover) and (pointer: fine)').matches;
        this.dragEnabled = (this.cfg.drag === null) ? !!auto : !!this.cfg.drag;
        if (!this.dragEnabled) { return; }
        var self = this;
        this._onDragStart = function (event) {
            var itemEl = event.target.closest('.pg-item');
            if (!itemEl) { return; }
            self.select(self._ids[itemEl.dataset.pgItem]);
        };
        this._onDragOver = function (event) {
            if (self.selectedId === null) { return; }
            var cellEl = event.target.closest('.pg-cell');
            if (cellEl) { event.preventDefault(); }
        };
        this._onDrop = function (event) {
            var cellEl = event.target.closest('.pg-cell');
            if (!cellEl || self.selectedId === null) { return; }
            event.preventDefault();
            self._placeInto(parseInt(cellEl.dataset.pgRow, 10),
                            parseInt(cellEl.dataset.pgCol, 10));
        };
        this.el.addEventListener('dragstart', this._onDragStart);
        this.el.addEventListener('dragover', this._onDragOver);
        this.el.addEventListener('drop', this._onDrop);
    }

    _unbindDrag() {
        if (!this._onDragStart) { return; }
        this.el.removeEventListener('dragstart', this._onDragStart);
        this.el.removeEventListener('dragover', this._onDragOver);
        this.el.removeEventListener('drop', this._onDrop);
    }

    /* ------------------------------------------------------------------ *
     * plumbing                                                            *
     * ------------------------------------------------------------------ */

    _emit(name, detail) {
        this.el.dispatchEvent(new CustomEvent(name, {
            detail: Object.assign({grid: this}, detail),
            bubbles: true, cancelable: false}));
    }

    _announce(message) { this.live.textContent = message; }

    _itemNode(id) {
        var nodes = this.rowsEl.querySelectorAll('[data-pg-item]');
        for (var i = 0; i < nodes.length; i++) {
            if (this._ids[nodes[i].dataset.pgItem] === id) { return nodes[i]; }
        }
        return null;
    }

    _cellNode(row, col) {
        return this.rowsEl.querySelector(
            '.pg-cell[data-pg-row="' + row + '"][data-pg-col="' + col + '"]');
    }

    _focusCell(row, col) {
        var node = this._cellNode(row, col);
        if (!node) { return; }
        this.rowsEl.querySelectorAll('.pg-cell[tabindex="0"]').forEach(
            function (el) { el.setAttribute('tabindex', '-1'); });
        node.setAttribute('tabindex', '0');
        node.focus();
    }

    _locate(id) {
        var cells = (this.data && this.data.cells) || [];
        for (var r = 0; r < cells.length; r++) {
            for (var c = 0; c < cells[r].length; c++) {
                if (cells[r][c].indexOf(id) !== -1) { return {row: r, col: c}; }
            }
        }
        return null;
    }

    _applySelection() {
        this.el.classList.toggle('pg-selecting', this.selectedId !== null);
        var self = this;
        this.rowsEl.querySelectorAll('.pg-item').forEach(function (node) {
            var selected = self._ids[node.dataset.pgItem] === self.selectedId &&
                           self.selectedId !== null;
            node.classList.toggle('pg-selected', selected);
            node.setAttribute('aria-pressed', selected ? 'true' : 'false');
        });
    }

    _captureFocus() {
        var active = document.activeElement;
        if (!active || !this.rowsEl.contains(active)) { return null; }
        var itemEl = active.closest('.pg-item');
        if (itemEl) { return {item: this._ids[itemEl.dataset.pgItem]}; }
        var cellEl = active.closest('.pg-cell');
        if (cellEl) {
            return {row: parseInt(cellEl.dataset.pgRow, 10),
                    col: parseInt(cellEl.dataset.pgCol, 10)};
        }
        return null;
    }

    _restoreFocus(focus) {
        var target = this._cellNode(this._active.row, this._active.col) ||
                     this._cellNode(0, 0);
        if (target) { target.setAttribute('tabindex', '0'); }
        if (!focus) { return; }
        if (focus.item !== undefined) {
            var node = this._itemNode(focus.item);
            if (node) { node.focus(); return; }
        }
        if (focus.row !== undefined) { this._focusCell(focus.row, focus.col); }
    }
}

window.PositionsGrid = PositionsGrid;
