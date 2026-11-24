/* The interactive grid of djgentelella.designs (``interactive_grid``).
 *
 * Rows of a model edited in place and saved together. The server leaves the
 * grid's configuration as JSON in a <script type="application/json"> and,
 * for each editable column, the widget of its field in a <template> whose
 * names carry `__row__`: a row being edited gets a copy of each one with its
 * own key there, booted with gt_find_initialize() and filled with
 * updateInstanceValuesForm() -- the same as a modal of object management.
 *
 * Nothing is written until "Save changes": then every new, changed and
 * deleted row goes in one POST to `save/`, which saves them all or none. A
 * row that fails keeps its changes and shows why: field errors under the
 * cell, the rest next to the row. A conflict (somebody else saved the row
 * after it was read, `code === 'version_conflict'`) offers to reload that
 * row alone, without losing the changes of the others.
 *
 * Everything that comes from a row is written as text, never as HTML.
 */
(function () {
    'use strict';

    var sequence = 0;

    function readJSON(id) {
        var element = document.getElementById(id);
        return element ? JSON.parse(element.textContent) : null;
    }

    function make(tag, className, text) {
        var element = document.createElement(tag);
        if (className) { element.className = className; }
        if (text !== undefined && text !== null) { element.textContent = text; }
        return element;
    }

    function button(className, icon, title) {
        var element = make('button', 'btn btn-sm btn-link p-0 me-2 ' + className);
        element.type = 'button';
        element.title = title;
        element.setAttribute('aria-label', title);
        element.appendChild(make('i', icon));
        return element;
    }

    function same(a, b) {
        return JSON.stringify(a === undefined ? null : a) === JSON.stringify(b === undefined ? null : b);
    }

    /* The text of a value in a cell that is not being edited. */
    function displayText(column, value) {
        if (value === null || value === undefined || value === '') { return ''; }
        if (column.kind === 'fk' || column.kind === 'o2o') {
            return typeof value === 'object' ? String(value.text === undefined ? '' : value.text) : String(value);
        }
        if (column.kind === 'm2m') {
            return (Array.isArray(value) ? value : [value]).map(function (item) {
                return item && typeof item === 'object' ? item.text : item;
            }).join(', ');
        }
        if (column.kind === 'boolean' || column.kind === 'nullboolean') {
            return value ? gettext('Yes') : gettext('No');
        }
        if (column.kind === 'choices') {
            var found = (column.choices || []).filter(function (choice) {
                return String(choice[0]) === String(value);
            });
            return found.length ? found[0][1] : String(value);
        }
        return String(value);
    }

    /* What updateInstanceValuesForm() expects for a value of the list: an
       autocomplete takes {id, text}, any other select the id. */
    function widgetValue(column, value) {
        if (column.kind === 'fk' || column.kind === 'o2o') {
            if (value === null || value === undefined) { return column.lookup ? null : ''; }
            return column.lookup ? value : value.id;
        }
        return value === null || value === undefined ? '' : value;
    }

    function Row(data, isNew) {
        sequence += 1;
        this.key = (isNew ? 'n' : 'r') + sequence;
        this.data = data || {};
        this.isNew = !!isNew;
        this.editing = false;
        this.deleted = false;
        this.dirty = false;
        this.initial = null;
        this.failure = null;
        this.tr = null;
    }

    function Grid(element) {
        var grid = this;
        this.element = element;
        this.config = readJSON(element.getAttribute('data-gtconfig'));
        this.columns = this.config.columns;
        this.table = element.querySelector('.gtgrid-table');
        this.tbody = this.table.tBodies[0];
        this.statusElement = element.querySelector('.gtgrid-status');
        this.saveButton = element.querySelector('.gtgrid-save');
        this.addButton = element.querySelector('.gtgrid-add');
        this.searchInput = element.querySelector('.gtgrid-search');
        this.prevButton = element.querySelector('.gtgrid-prev');
        this.nextButton = element.querySelector('.gtgrid-next');
        this.info = element.querySelector('.gtgrid-info');
        this.templates = {};
        element.querySelectorAll('template[data-gtgrid-cell]').forEach(function (template) {
            grid.templates[template.getAttribute('data-gtgrid-cell')] = template.innerHTML;
        });
        this.rows = [];
        this.offset = 0;
        this.count = 0;
        this.search = '';
        this.busy = false;
        this.drawHead();
        this.bind();
        this.load();
    }

    Grid.prototype = {
        url: function (rest) {
            return this.config.url + (rest || '');
        },

        headers: function (json) {
            var headers = {'X-CSRFToken': getCookie('csrftoken'), 'Accept': 'application/json'};
            if (json) { headers['Content-Type'] = 'application/json'; }
            return headers;
        },

        setStatus: function (text, kind) {
            this.statusElement.textContent = text || '';
            this.statusElement.className = 'gtgrid-status ms-2' + (kind ? ' text-' + kind : '');
        },

        drawHead: function () {
            var tr = make('tr');
            this.columns.forEach(function (column) {
                var th = make('th', null, column.title);
                th.setAttribute('data-column', column.name);
                tr.appendChild(th);
            });
            tr.appendChild(make('th', 'gtgrid-actions-head'));
            this.table.tHead.appendChild(tr);
        },

        bind: function () {
            var grid = this;
            $(this.tbody).on('click', 'button', function (event) {
                var row = grid.rowOf(this);
                if (!row) { return; }
                event.preventDefault();
                if (this.classList.contains('gtgrid-edit')) { grid.startEdit(row); }
                else if (this.classList.contains('gtgrid-delete')) { grid.toggleDelete(row); }
                else if (this.classList.contains('gtgrid-undo')) { grid.undo(row); }
                else if (this.classList.contains('gtgrid-reload')) { grid.reload(row); }
            });
            // A click on a cell that can be edited starts editing its row.
            $(this.tbody).on('click', 'td.gtgrid-can-edit', function () {
                var row = grid.rowOf(this);
                if (row && !row.editing && !row.deleted) {
                    grid.startEdit(row, this.getAttribute('data-column'));
                }
            });
            // select2 and the other widgets trigger jQuery events, not
            // native ones: listen with jQuery.
            $(this.tbody).on('input change', 'input, select, textarea', function () {
                var row = grid.rowOf(this);
                if (row) { grid.refreshDirty(row); }
            });
            if (this.saveButton) {
                this.saveButton.addEventListener('click', function () { grid.save(); });
            }
            if (this.addButton) {
                this.addButton.addEventListener('click', function () { grid.addRow(); });
            }
            this.prevButton.addEventListener('click', function () { grid.page(-1); });
            this.nextButton.addEventListener('click', function () { grid.page(1); });
            if (this.searchInput && this.config.search) {
                var timer = null;
                this.searchInput.classList.remove('d-none');
                this.searchInput.addEventListener('input', function () {
                    clearTimeout(timer);
                    timer = setTimeout(function () {
                        if (grid.pending()) {
                            grid.searchInput.value = grid.search;
                            grid.setStatus(gettext('Save or undo your changes first.'), 'warning');
                            return;
                        }
                        grid.search = grid.searchInput.value;
                        grid.offset = 0;
                        grid.load();
                    }, 400);
                });
            }
        },

        rowOf: function (node) {
            var tr = node.closest('tr[data-key]');
            if (!tr) { return null; }
            var key = tr.getAttribute('data-key');
            for (var index = 0; index < this.rows.length; index++) {
                if (this.rows[index].key === key) { return this.rows[index]; }
            }
            return null;
        },

        pending: function () {
            return this.rows.some(function (row) {
                return row.isNew || row.deleted || row.dirty;
            });
        },

        refreshButtons: function () {
            var pending = this.pending();
            if (this.saveButton) { this.saveButton.disabled = !pending || this.busy; }
            this.prevButton.disabled = pending || this.offset <= 0;
            this.nextButton.disabled = pending || this.offset + this.config.page_size >= this.count;
            if (this.searchInput) { this.searchInput.disabled = pending; }
            var first = this.count ? this.offset + 1 : 0;
            var last = Math.min(this.offset + this.config.page_size, this.count);
            this.info.textContent = first + '-' + last + ' / ' + this.count;
        },

        // -- reading -----------------------------------------------------------------

        load: function () {
            var grid = this;
            var params = new URLSearchParams({limit: this.config.page_size, offset: this.offset});
            if (this.search) { params.set('search', this.search); }
            return fetch(this.url('?' + params.toString()), {headers: this.headers(false)})
                .then(function (response) {
                    if (!response.ok) { throw new Error(response.statusText); }
                    return response.json();
                })
                .then(function (data) {
                    grid.rows = data.data.map(function (item) { return new Row(item, false); });
                    grid.count = data.count;
                    grid.tbody.innerHTML = '';
                    grid.rows.forEach(function (row) { grid.drawRow(row); });
                    if (!grid.rows.length) {
                        var tr = make('tr');
                        var td = make('td', 'text-center text-muted gtgrid-empty', gettext('No rows'));
                        td.colSpan = grid.columns.length + 1;
                        tr.appendChild(td);
                        grid.tbody.appendChild(tr);
                    }
                    grid.refreshButtons();
                })
                .catch(function () {
                    grid.setStatus(gettext('The rows could not be read.'), 'danger');
                });
        },

        page: function (step) {
            if (this.pending()) {
                this.setStatus(gettext('Save or undo your changes first.'), 'warning');
                return;
            }
            this.offset = Math.max(0, this.offset + step * this.config.page_size);
            this.load();
        },

        // -- drawing -----------------------------------------------------------------

        canEdit: function (row, column) {
            if (!column.editable || this.templates[column.name] === undefined) { return false; }
            if (row.isNew) { return !!this.config.allowed.create; }
            var actions = row.data.actions || {};
            return !!actions.update && (row.data.readonly || []).indexOf(column.name) < 0;
        },

        editable: function (row) {
            var grid = this;
            return this.columns.some(function (column) { return grid.canEdit(row, column); });
        },

        prefix: function (row) {
            return this.config.prefix + '-' + row.key + '-';
        },

        drawRow: function (row) {
            var grid = this;
            var tr = make('tr');
            tr.setAttribute('data-key', row.key);
            if (row.data.id !== undefined && row.data.id !== null) {
                tr.setAttribute('data-id', row.data.id);
            }
            this.columns.forEach(function (column) {
                var td = make('td');
                td.setAttribute('data-column', column.name);
                if (row.editing && grid.canEdit(row, column)) {
                    td.className = 'gtgrid-cell-editing';
                    td.innerHTML = grid.templates[column.name].split('__row__').join(row.key);
                } else {
                    td.textContent = displayText(column, row.data[column.name]);
                    if (!row.editing && !row.deleted && grid.canEdit(row, column)) {
                        td.classList.add('gtgrid-can-edit');
                    }
                }
                tr.appendChild(td);
            });
            tr.appendChild(make('td', 'gtgrid-row-actions text-nowrap'));
            if (row.tr && row.tr.parentNode) {
                row.tr.parentNode.replaceChild(tr, row.tr);
            } else {
                var empty = this.tbody.querySelector('.gtgrid-empty');
                if (empty) { empty.parentNode.remove(); }
                this.tbody.appendChild(tr);
            }
            row.tr = tr;
            this.drawState(row);
        },

        /* The classes, buttons and message of a row, without touching the
           cells being edited. */
        drawState: function (row) {
            var tr = row.tr;
            tr.classList.toggle('gtgrid-new', row.isNew);
            tr.classList.toggle('gtgrid-changed', row.dirty);
            tr.classList.toggle('table-warning', row.dirty || row.isNew);
            tr.classList.toggle('gtgrid-deleted', row.deleted);
            tr.classList.toggle('text-decoration-line-through', row.deleted);
            tr.classList.toggle('gtgrid-failed', !!row.failure);
            tr.classList.toggle('table-danger', row.deleted || !!row.failure);
            tr.classList.toggle('gtgrid-conflict', !!row.failure && row.failure.code === 'version_conflict');
            var cell = tr.lastChild;
            cell.innerHTML = '';
            var actions = row.data.actions || {};
            if (!row.editing && !row.deleted && !row.isNew && this.editable(row)) {
                cell.appendChild(button('gtgrid-edit', 'fa fa-pencil', gettext('Edit')));
            }
            if (!row.deleted && (row.isNew || actions.destroy)) {
                cell.appendChild(button('gtgrid-delete', 'fa fa-trash', gettext('Delete')));
            }
            if (!row.isNew && (row.editing || row.deleted)) {
                cell.appendChild(button('gtgrid-undo', 'fa fa-undo', gettext('Undo the changes of this row')));
            }
            if (row.failure && (row.failure.code === 'version_conflict' || row.failure.code === 'not_found')) {
                cell.appendChild(button('gtgrid-reload', 'fa fa-refresh', gettext('Reload this row')));
            }
            if (row.failure) {
                var message = make('div', 'gtgrid-message small text-danger text-wrap');
                var texts = [row.failure.detail || ''];
                var grid = this;
                Object.keys(row.failure.errors || {}).forEach(function (name) {
                    // Errors of a field without a cell being edited go here.
                    if (!row.tr.querySelector('td[data-column="' + CSS.escape(name) + '"].gtgrid-cell-editing')) {
                        var column = grid.columns.filter(function (item) { return item.name === name; })[0];
                        texts.push((column ? column.title : name) + ': ' + [].concat(row.failure.errors[name]).join(' '));
                    }
                });
                message.textContent = texts.filter(Boolean).join(' ');
                cell.appendChild(message);
            }
            this.refreshButtons();
        },

        clearErrors: function (row) {
            if (!row.tr) { return; }
            row.tr.querySelectorAll('.gtgrid-error').forEach(function (node) { node.remove(); });
            row.tr.querySelectorAll('.is-invalid').forEach(function (node) {
                node.classList.remove('is-invalid');
            });
        },

        showErrors: function (row) {
            this.clearErrors(row);
            var errors = (row.failure && row.failure.errors) || {};
            Object.keys(errors).forEach(function (name) {
                var td = row.tr.querySelector('td[data-column="' + CSS.escape(name) + '"].gtgrid-cell-editing');
                if (!td) { return; }
                td.querySelectorAll('input, select, textarea').forEach(function (input) {
                    input.classList.add('is-invalid');
                });
                td.appendChild(make('div', 'invalid-feedback d-block gtgrid-error',
                    [].concat(errors[name]).join(' ')));
            });
            this.drawState(row);
        },

        // -- editing -----------------------------------------------------------------

        startEdit: function (row, focus) {
            var grid = this;
            if (row.editing || !this.editable(row)) { return; }
            row.editing = true;
            row.initial = null;
            this.drawRow(row);
            var $tr = $(row.tr);
            gt_find_initialize($tr);
            if (!row.isNew) {
                var prefix = this.prefix(row);
                this.columns.forEach(function (column) {
                    if (grid.canEdit(row, column)) {
                        updateInstanceValuesForm($tr, prefix + column.name,
                            widgetValue(column, row.data[column.name]));
                    }
                });
            }
            // What the row holds before the user touches it, read the same
            // way it will be read to save: only real changes count.
            return this.collect(row).then(function (values) {
                row.initial = values;
                if (focus) {
                    var input = row.tr.querySelector('td[data-column="' + CSS.escape(focus) + '"] input:not([type=hidden]), ' +
                        'td[data-column="' + CSS.escape(focus) + '"] select, td[data-column="' + CSS.escape(focus) + '"] textarea');
                    if (input) { input.focus(); }
                }
                grid.drawState(row);
            });
        },

        collect: function (row) {
            var tr = row.tr;
            var names = this.columns.filter(function (column) {
                return tr.querySelector('td[data-column="' + CSS.escape(column.name) + '"].gtgrid-cell-editing');
            }).map(function (column) { return column.name; });
            var form = {
                elements: tr.querySelectorAll('td.gtgrid-cell-editing input, td.gtgrid-cell-editing select, td.gtgrid-cell-editing textarea'),
                querySelectorAll: function (selector) { return tr.querySelectorAll(selector); }
            };
            return obtainFormAsJSON(form, this.prefix(row), {}, false).then(function (data) {
                var values = {};
                names.forEach(function (name) {
                    if (Object.prototype.hasOwnProperty.call(data, name)) { values[name] = data[name]; }
                });
                return values;
            });
        },

        changes: function (row, values) {
            var result = {};
            Object.keys(values).forEach(function (name) {
                if (!row.initial || !same(values[name], row.initial[name])) { result[name] = values[name]; }
            });
            return result;
        },

        refreshDirty: function (row) {
            var grid = this;
            if (!row.editing || row.initial === null || row.isNew) { return; }
            this.collect(row).then(function (values) {
                var dirty = Object.keys(grid.changes(row, values)).length > 0;
                if (dirty !== row.dirty) {
                    row.dirty = dirty;
                    grid.drawState(row);
                }
            });
        },

        addRow: function () {
            var row = new Row({}, true);
            this.rows.push(row);
            this.drawRow(row);
            this.startEdit(row);
        },

        remove: function (row) {
            if (row.tr) { row.tr.remove(); }
            this.rows = this.rows.filter(function (item) { return item !== row; });
            this.refreshButtons();
        },

        toggleDelete: function (row) {
            if (row.isNew) { this.remove(row); return; }
            row.deleted = !row.deleted;
            this.drawState(row);
        },

        undo: function (row) {
            if (row.isNew) { this.remove(row); return; }
            row.editing = false;
            row.deleted = false;
            row.dirty = false;
            row.initial = null;
            row.failure = null;
            this.drawRow(row);
        },

        /* The row as the server has it now; its changes are dropped, those
           of the other rows are kept. */
        reload: function (row) {
            var grid = this;
            fetch(this.url(encodeURIComponent(row.data.id) + '/'), {headers: this.headers(false)})
                .then(function (response) {
                    if (response.status === 404 || response.status === 403) {
                        grid.remove(row);
                        grid.count = Math.max(0, grid.count - 1);
                        grid.refreshButtons();
                        grid.setStatus(gettext('That row is no longer available.'), 'warning');
                        return null;
                    }
                    if (!response.ok) { throw new Error(response.statusText); }
                    return response.json();
                })
                .then(function (data) {
                    if (data === null) { return; }
                    row.data = data;
                    grid.undo(row);
                    grid.setStatus(gettext('The row was reloaded with the current data.'), 'info');
                })
                .catch(function () {
                    grid.setStatus(gettext('The row could not be read.'), 'danger');
                });
        },

        // -- saving ------------------------------------------------------------------

        save: function () {
            var grid = this;
            if (this.busy) { return; }
            var rows = this.rows.slice();
            Promise.all(rows.map(function (row) {
                return row.editing && !row.deleted ? grid.collect(row) : Promise.resolve(null);
            })).then(function (collected) {
                var batch = [];
                rows.forEach(function (row, index) {
                    var values = collected[index];
                    if (row.deleted) {
                        batch.push({key: row.key, op: 'delete', id: row.data.id,
                                    _version: row.data._version});
                    } else if (row.isNew) {
                        batch.push({key: row.key, op: 'create', data: values || {}});
                    } else if (values) {
                        var changes = grid.changes(row, values);
                        if (Object.keys(changes).length) {
                            batch.push({key: row.key, op: 'update', id: row.data.id,
                                        _version: row.data._version, data: changes});
                        }
                    }
                });
                if (!batch.length) {
                    grid.setStatus(gettext('Nothing to save.'), 'muted');
                    return null;
                }
                grid.busy = true;
                grid.refreshButtons();
                grid.setStatus(gettext('Saving...'), 'muted');
                return fetch(grid.url('save/'), {
                    method: 'POST', headers: grid.headers(true),
                    body: JSON.stringify({rows: batch})
                }).then(function (response) {
                    return response.json().then(function (data) {
                        return {ok: response.ok, data: data};
                    }, function () {
                        return {ok: false, data: {detail: response.statusText}};
                    });
                }).then(function (result) {
                    grid.busy = false;
                    if (result.ok) { grid.saved(result.data); } else { grid.failed(result.data); }
                });
            }).catch(function () {
                grid.busy = false;
                grid.refreshButtons();
                grid.setStatus(gettext('The changes could not be saved.'), 'danger');
            });
        },

        byKey: function (key) {
            return this.rows.filter(function (row) { return row.key === key; })[0] || null;
        },

        saved: function (data) {
            var grid = this;
            (data.rows || []).forEach(function (item) {
                var row = grid.byKey(item.key);
                if (!row) { return; }
                if (item.op === 'delete' || !item.row) {
                    grid.remove(row);
                    if (item.op === 'delete') { grid.count = Math.max(0, grid.count - 1); }
                    return;
                }
                if (row.isNew) { grid.count += 1; }
                row.data = item.row;
                row.isNew = false;
                grid.undo(row);
            });
            this.rows.forEach(function (row) { row.failure = null; });
            this.refreshButtons();
            this.setStatus(gettext('Saved.'), 'success');
        },

        failed: function (data) {
            var grid = this;
            this.rows.forEach(function (row) {
                if (row.failure) {
                    row.failure = null;
                    if (row.tr) { grid.clearErrors(row); grid.drawState(row); }
                }
            });
            (data.rows || []).forEach(function (failure) {
                var row = grid.byKey(failure.key);
                if (!row) { return; }
                row.failure = failure;
                grid.showErrors(row);
            });
            this.refreshButtons();
            this.setStatus(data.detail || gettext('The changes could not be saved.'), 'danger');
        }
    };

    function init() {
        document.querySelectorAll('.gtdesign-grid[data-gtconfig]').forEach(function (element) {
            if (!element.gtgrid) { element.gtgrid = new Grid(element); }
        });
    }

    window.GTInteractiveGrid = Grid;
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
