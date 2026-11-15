/* Widgets of djgentelella.datasources: the facets panel (GTFacets), its chips
 * version (GTFacetChips, APEX's smart filters), the export menu
 * (GTDataSourceExport) and gtCreateDataSourceTable, a DataTable fed by a data
 * source.
 *
 * The widgets never talk to each other. Every widget of a page that names the
 * same data source url (and data-group, when there are two tables over one
 * source) shares one GTDataSourceState: the facets write their filter into
 * it, and the table, the other facets, the chips and the export menu listen
 * to it and reload. The state is the query parameter document, so what a
 * page sends to `rows`, `facets` and `export` is the same JSON a saved report
 * stores.
 *
 * Classes, so this file goes in createbasejs' `basefiles`, never in
 * `jquery_plugins` (see positionsgrid.js); nothing here runs at load time.
 */

class GTDataSourceState {
    constructor(url, base) {
        this.url = url.endsWith('/') ? url : url + '/';
        this.base = Object.assign({}, base || {});
        this.facetFilters = {};   // column -> filter, one per column
        this.search = '';
        this.ordering = null;
        this.labels = {};         // column -> {JSON(value): label}
        this.listeners = [];
        this.searchListeners = [];
        this._info = null;
    }

    info() {
        if (this._info === null) {
            this._info = fetch(this.url, {credentials: 'same-origin',
                                          headers: {'Accept': 'application/json'}})
                .then(function (response) {
                    if (!response.ok) { throw new Error(response.status); }
                    return response.json();
                });
        }
        return this._info;
    }

    column(info, name) {
        return info.columns.find(function (c) { return c.name === name; });
    }

    /* The query parameter document: the base params of the page, the facet
       filters and the table's search and ordering. */
    params() {
        var params = JSON.parse(JSON.stringify(this.base));
        var self = this;
        params.filters = (params.filters || []).concat(
            Object.keys(this.facetFilters).map(function (k) { return self.facetFilters[k]; }));
        if (this.search) { params.search = this.search; }
        if (this.ordering) { params.ordering = [this.ordering].concat(params.ordering || []); }
        return params;
    }

    setFilter(column, filter) {
        if (filter === null || filter === undefined) {
            delete this.facetFilters[column];
        } else {
            this.facetFilters[column] = Object.assign({column: column}, filter);
        }
        this.notify();
    }

    clear() {
        this.facetFilters = {};
        this.notify();
    }

    remember(column, entries) {
        var labels = this.labels[column] = this.labels[column] || {};
        entries.forEach(function (e) { labels[JSON.stringify(e.value)] = e.label; });
    }

    label(column, value) {
        var labels = this.labels[column] || {};
        var key = JSON.stringify(value);
        return key in labels ? labels[key] : String(value);
    }

    subscribe(fn) { this.listeners.push(fn); }

    /* Called when the table's own search box changes: the facets recount,
       the table needs nothing (it is the one that searched). */
    subscribeSearch(fn) { this.searchListeners.push(fn); }

    setSearch(text) {
        if (text === this.search) { return; }
        this.search = text;
        var self = this;
        this.searchListeners.forEach(function (fn) { fn(self); });
    }

    notify() {
        var self = this;
        this.listeners.forEach(function (fn) { fn(self); });
    }

    /* ``<url><endpoint>/?<params>``: with the trailing slash, which the data
     * source API takes either way and the design router (`gtapis/designs/...`) requires. */
    query(endpoint, extra) {
        var qs = new URLSearchParams(Object.assign(
            {params: JSON.stringify(this.params())}, extra || {}));
        return this.url + endpoint + '/?' + qs.toString();
    }

    facets(columns) {
        return fetch(this.query('facets', {columns: columns.join(',')}),
                     {credentials: 'same-origin'})
            .then(function (response) {
                if (!response.ok) { throw new Error(response.status); }
                return response.json();
            });
    }

    exportUrl(fmt) { return this.query('export', {fmt: fmt}); }
}

document.gt_datasource_states = {};

/* The state shared by every widget over `url` (and `group`). */
function gt_datasource_state(url, group, base) {
    var key = (group || '') + '|' + url;
    if (!(key in document.gt_datasource_states)) {
        document.gt_datasource_states[key] = new GTDataSourceState(url, base);
    } else if (base) {
        Object.assign(document.gt_datasource_states[key].base, base);
    }
    return document.gt_datasource_states[key];
}

function gt_datasource_state_from(element) {
    var $e = $(element);
    var base = $e.data('params') || null;
    return gt_datasource_state($e.data('url'), $e.data('group'), base);
}

function gt_facet_text(entry) {
    return entry.label + ' (' + entry.count + ')';
}

function gt_facet_is_selected(filter, entry) {
    if (!filter) { return false; }
    var value = JSON.stringify(entry.value);
    if (entry.op === 'in' && filter.op === 'in') {
        return (filter.value || []).some(function (v) { return JSON.stringify(v) === value; });
    }
    return filter.op === entry.op && JSON.stringify(filter.value) === value;
}

/* The filter that results from clicking `entry` with `filter` in place:
   `in` facets add and remove values, the others replace. */
function gt_facet_toggle(filter, entry) {
    if (entry.op === 'in') {
        var values = (filter && filter.op === 'in') ? filter.value.slice() : [];
        var value = JSON.stringify(entry.value);
        var at = values.findIndex(function (v) { return JSON.stringify(v) === value; });
        if (at >= 0) { values.splice(at, 1); } else { values.push(entry.value); }
        return values.length ? {op: 'in', value: values} : null;
    }
    if (gt_facet_is_selected(filter, entry)) { return null; }
    return {op: entry.op, value: entry.op === 'isnull' ? true : entry.value};
}

/* A range ("from", "to") under the numeric and date facets. */
function gt_facet_range(state, column, kind) {
    var type = kind === 'date' || kind === 'datetime' ? 'date' : 'number';
    var filter = state.facetFilters[column.name];
    var current = filter && filter.op === 'between' ? filter.value : ['', ''];
    var $range = $('<div class="input-group input-group-sm mt-1 gt-facet-range"></div>');
    var $low = $('<input class="form-control">').attr({type: type, placeholder: gettext('From')})
        .val(current[0] === null ? '' : current[0]);
    var $high = $('<input class="form-control">').attr({type: type, placeholder: gettext('To')})
        .val(current[1] === null ? '' : current[1]);
    var $apply = $('<button type="button" class="btn btn-outline-secondary"></button>')
        .attr('title', gettext('Apply')).append('<i class="fa fa-filter"></i>');
    $apply.on('click', function () {
        var low = $low.val(), high = $high.val();
        state.setFilter(column.name, (low === '' && high === '') ? null :
                        {op: 'between', value: [low === '' ? null : low, high === '' ? null : high]});
    });
    return $range.append($low, $high, $apply);
}

/* The side panel: one block per column, checkboxes with counts for values,
   radios for ranges and periods, and a from/to range under the numeric and
   date ones. */
class GTFacets {
    constructor(element) {
        this.$el = $(element);
        this.columns = String(this.$el.data('columns') || '').split(',').filter(Boolean);
        this.state = gt_datasource_state_from(element);
        var self = this;
        this.state.subscribe(function () { self.load(); });
        this.state.subscribeSearch(function () { self.load(); });
        this.load();
    }

    load() {
        var self = this;
        Promise.all([this.state.info(), this.state.facets(this.columns)])
            .then(function (result) { self.render(result[0], result[1]); })
            .catch(function () {
                self.$el.empty().append($('<div class="text-danger small"></div>')
                    .text(gettext('The filters could not be loaded.')));
            });
    }

    render(info, facets) {
        var self = this;
        var state = this.state;
        this.$el.empty().addClass('gt-facets');
        if (Object.keys(state.facetFilters).length) {
            $('<button type="button" class="btn btn-link btn-sm p-0 mb-2"></button>')
                .text(gettext('Clear all')).on('click', function () { state.clear(); })
                .appendTo(this.$el);
        }
        this.columns.forEach(function (name) {
            var column = state.column(info, name) || {name: name, label: name, kind: 'string'};
            var entries = facets[name] || [];
            state.remember(name, entries);
            var filter = state.facetFilters[name];
            var $block = $('<div class="gt-facet mb-3"></div>').attr('data-column', name);
            var $title = $('<div class="d-flex justify-content-between align-items-center"></div>')
                .append($('<strong class="small"></strong>').text(column.label));
            if (filter) {
                $('<button type="button" class="btn btn-link btn-sm p-0"></button>')
                    .text(gettext('Clear')).on('click', function () { state.setFilter(name, null); })
                    .appendTo($title);
            }
            $block.append($title);
            var multiple = entries.length && entries[0].op === 'in';
            entries.forEach(function (entry, i) {
                var id = 'gtfacet_' + name.replace(/\W/g, '_') + '_' + i + '_' + Math.random().toString(36).slice(2, 7);
                var $check = $('<input class="form-check-input">')
                    .attr({type: multiple ? 'checkbox' : 'radio', id: id, name: 'gtfacet_' + name})
                    .prop('checked', gt_facet_is_selected(filter, entry));
                $check.on('change', function () {
                    state.setFilter(name, gt_facet_toggle(state.facetFilters[name], entry));
                });
                $('<div class="form-check"></div>')
                    .append($check, $('<label class="form-check-label small"></label>')
                        .attr('for', id).text(gt_facet_text(entry)))
                    .toggleClass('text-muted', entry.count === 0)
                    .appendTo($block);
            });
            if (!entries.length) {
                $block.append($('<div class="small text-muted"></div>').text(gettext('No data')));
            }
            if (['integer', 'decimal', 'date', 'datetime'].indexOf(column.kind) >= 0) {
                $block.append(gt_facet_range(state, column, column.kind));
            }
            self.$el.append($block);
        });
    }
}

/* Smart filters: the active filters as removable chips, and one dropdown per
   column listing its values with their counts. */
class GTFacetChips {
    constructor(element) {
        this.$el = $(element);
        this.columns = String(this.$el.data('columns') || '').split(',').filter(Boolean);
        this.state = gt_datasource_state_from(element);
        var self = this;
        this.state.subscribe(function () { self.load(); });
        this.state.subscribeSearch(function () { self.load(); });
        this.load();
    }

    load() {
        var self = this;
        Promise.all([this.state.info(), this.state.facets(this.columns)])
            .then(function (result) { self.render(result[0], result[1]); })
            .catch(function () { self.$el.empty(); });
    }

    chipText(column, filter) {
        var state = this.state;
        var value;
        if (filter.op === 'in') {
            value = filter.value.map(function (v) { return state.label(column.name, v); }).join(', ');
        } else if (filter.op === 'between') {
            value = (filter.value[0] === null ? '…' : filter.value[0]) + ' – ' +
                    (filter.value[1] === null ? '…' : filter.value[1]);
        } else if (filter.op === 'isnull') {
            value = gettext('Empty');
        } else {
            value = state.label(column.name, filter.value);
        }
        return column.label + ': ' + value;
    }

    render(info, facets) {
        var self = this;
        var state = this.state;
        this.$el.empty().addClass('gt-facet-chips d-flex flex-wrap align-items-center gap-1');
        Object.keys(state.facetFilters).forEach(function (name) {
            var column = state.column(info, name) || {name: name, label: name};
            var $chip = $('<span class="badge rounded-pill text-bg-primary gt-facet-chip"></span>')
                .attr('data-column', name).text(self.chipText(column, state.facetFilters[name]));
            $('<button type="button" class="btn-close btn-close-white ms-1"></button>')
                .attr('aria-label', gettext('Remove'))
                .css({'font-size': '0.6em', 'vertical-align': 'middle'})
                .on('click', function () { state.setFilter(name, null); })
                .appendTo($chip);
            self.$el.append($chip);
        });
        this.columns.forEach(function (name) {
            var column = state.column(info, name) || {name: name, label: name};
            var entries = facets[name] || [];
            state.remember(name, entries);
            var $group = $('<div class="dropdown d-inline-block"></div>');
            $('<button type="button" class="btn btn-sm btn-outline-secondary dropdown-toggle" data-bs-toggle="dropdown"></button>')
                .text(column.label).appendTo($group);
            var $menu = $('<ul class="dropdown-menu"></ul>').appendTo($group);
            entries.forEach(function (entry) {
                var $item = $('<a class="dropdown-item small" href="#"></a>').text(gt_facet_text(entry))
                    .toggleClass('active', gt_facet_is_selected(state.facetFilters[name], entry));
                $item.on('click', function (event) {
                    event.preventDefault();
                    state.setFilter(name, gt_facet_toggle(state.facetFilters[name], entry));
                });
                $('<li></li>').append($item).appendTo($menu);
            });
            if (!entries.length) {
                $('<li><span class="dropdown-item-text small text-muted"></span></li>')
                    .find('span').text(gettext('No data')).end().appendTo($menu);
            }
            self.$el.append($group);
        });
    }
}

var GT_EXPORT_FORMATS = {
    csv: {label: 'CSV', icon: 'fa fa-file-text-o'},
    xlsx: {label: 'Excel', icon: 'fa fa-file-excel-o'},
    json: {label: 'JSON', icon: 'fa fa-file-code-o'},
    pdf: {label: 'PDF', icon: 'fa fa-file-pdf-o'}
};

/* The order the export menus list `formats` in: the built-in ones as in
   GT_EXPORT_FORMATS (csv, xlsx, json, pdf), then the rest by name. The info
   endpoint lists them sorted, so the table reorders them for its menu. */
function gt_datasource_menu_formats(formats) {
    var builtin = Object.keys(GT_EXPORT_FORMATS);
    var first = builtin.filter(function (fmt) { return formats.indexOf(fmt) !== -1; });
    var rest = formats.filter(function (fmt) { return builtin.indexOf(fmt) === -1; }).sort();
    return first.concat(rest);
}

function gt_datasource_download(state, fmt) {
    window.location.href = state.exportUrl(fmt);
}

/* An export dropdown: each format downloads the rows the page shows now. */
class GTDataSourceExport {
    constructor(element) {
        this.$el = $(element);
        this.state = gt_datasource_state_from(element);
        var formats = String(this.$el.data('formats') || 'csv,xlsx,json,pdf').split(',');
        var state = this.state;
        var $group = $('<div class="dropdown d-inline-block gt-datasource-export"></div>');
        $('<button type="button" class="btn btn-sm btn-outline-secondary dropdown-toggle" data-bs-toggle="dropdown"></button>')
            .append('<i class="fa fa-download"></i> ').append(document.createTextNode(gettext('Export')))
            .appendTo($group);
        var $menu = $('<ul class="dropdown-menu"></ul>').appendTo($group);
        formats.forEach(function (fmt) {
            var spec = GT_EXPORT_FORMATS[fmt] || {label: fmt.toUpperCase(), icon: 'fa fa-file-o'};
            $('<a class="dropdown-item" href="#"></a>').attr('data-format', fmt)
                .append($('<i></i>').addClass(spec.icon), ' ', document.createTextNode(spec.label))
                .on('click', function (event) {
                    event.preventDefault();
                    gt_datasource_download(state, fmt);
                })
                .appendTo($('<li></li>').appendTo($menu));
        });
        this.$el.empty().append($group);
    }
}

/* A DataTables Buttons entry that exports the table's data source. */
function gt_datasource_export_button(state, formats) {
    return {
        extend: 'collection',
        text: '<i class="fa fa-download" aria-hidden="true"></i>',
        titleAttr: gettext('Export'),
        className: 'btn-outline-secondary',
        buttons: (formats || ['csv', 'xlsx', 'json', 'pdf']).map(function (fmt) {
            var spec = GT_EXPORT_FORMATS[fmt] || {label: fmt.toUpperCase()};
            return {text: gt_datasource_escape(spec.label), action: function () { gt_datasource_download(state, fmt); }};
        })
    };
}

/* `value` as HTML text: DataTables puts what a renderer returns, and a
   column's title, into the page as HTML, and the values come from users. */
function gt_datasource_escape(value) {
    var map = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'};
    return (value === null || value === undefined ? '' : String(value))
        .replace(/[&<>"']/g, function (c) { return map[c]; });
}

/* The `display_name` of a related object, escaped; '---' when there is none. */
function gt_datasource_display(obj) {
    if (obj === null || obj === undefined) { return null; }
    if (typeof obj !== 'object') { return gt_datasource_escape(obj); }
    return gt_datasource_escape(obj.display_name);
}

function gt_datasource_render(column) {
    if (column.kind === 'fk') {
        return function (data, type) {
            if (type !== 'display') { return data && typeof data === 'object' ? data.display_name : data; }
            var text = gt_datasource_display(data);
            return text === null ? '---' : text;
        };
    }
    if (column.kind === 'm2m') {
        return function (data, type) {
            var items = data === null || data === undefined ? [] : (Array.isArray(data) ? data : [data]);
            if (type !== 'display') {
                return items.map(function (o) { return o && typeof o === 'object' ? o.display_name : o; }).join(', ');
            }
            var texts = items.map(gt_datasource_display).filter(function (t) { return t !== null; });
            return texts.length ? texts.join('<br>') : '---';
        };
    }
    if (column.kind === 'boolean') { return yesnoprint; }
    if (column.kind === 'datetime') {
        // DRF sends UTC; show it in the browser's zone.
        return function (data, type) {
            if (!data || type !== 'display') { return data; }
            var date = new Date(data);
            return gt_datasource_escape(isNaN(date.getTime()) ? data : date.toLocaleString());
        };
    }
    if (column.kind === 'choices') {
        var labels = {};
        (column.choices || []).forEach(function (c) { labels[c[0]] = c[1]; });
        return function (data) { return data === null ? '' : gt_datasource_escape(labels[data] !== undefined ? labels[data] : data); };
    }
    return $.fn.dataTable.render.text();
}

/* The DataTables column definitions of a data source's columns. */
function gt_datasource_columns(info, names) {
    var columns = info.columns;
    if (names && names.length) {
        columns = names.map(function (n) { return columns.find(function (c) { return c.name === n; }); })
            .filter(Boolean);
    }
    return columns.map(function (c) {
        return {data: c.name, name: c.name, title: gt_datasource_escape(c.label), orderable: c.sortable,
                visible: true, render: gt_datasource_render(c)};
    });
}

/* A server side DataTable over a data source, wired to its shared state: the
   facets and chips of the same url reload it, its search box and ordering go
   into the parameters, and the export button downloads what it shows.

   options: columns (names to show; all by default), group, params (base
   parameter document), formats (export formats; [] for no button), and any
   gtCreateDataTable option. Returns a Promise of the DataTable. */
function gtCreateDataSourceTable(id, url, options) {
    options = Object.assign({}, options || {});
    var state = gt_datasource_state(url, options.group, options.params);
    var names = options.columns;
    var formats = options.formats;
    delete options.columns; delete options.group; delete options.params; delete options.formats;
    return state.info().then(function (info) {
        var columns = gt_datasource_columns(info, names);
        // Without formats, the ones the source offers this request.
        if (formats === undefined && Array.isArray(info.formats)) { formats = gt_datasource_menu_formats(info.formats); }
        if (names && names.length) { state.base.columns = names; }
        var buttons = [{
            action: function (e, dt) { state.clear(); dt.search('').draw(); },
            text: '<i class="fa fa-eraser" aria-hidden="true"></i>',
            titleAttr: gettext('Clear Filters'),
            className: 'btn-outline-secondary mr-4'
        }];
        if (!formats || formats.length) {
            buttons.push(gt_datasource_export_button(state, formats));
        }
        var table = gtCreateDataTable(id, state.url + 'rows', Object.assign({
            columns: columns,
            buttons: buttons,
            formatDataTableParamsfnc: function (dataTableParams, settings) {
                state.ordering = null;
                if (dataTableParams.order.length) {
                    var col = dataTableParams.columns[dataTableParams.order[0].column].name;
                    state.ordering = (dataTableParams.order[0].dir === 'desc' ? '-' : '') + col;
                }
                state.setSearch(dataTableParams.search.value || '');
                return {offset: dataTableParams.start, limit: dataTableParams.length,
                        draw: dataTableParams.draw, params: JSON.stringify(state.params())};
            }
        }, options));
        state.subscribe(function () { table.ajax.reload(); });
        return table;
    });
}
