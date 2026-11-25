/* The components with data of djgentelella.designs, in the browser.
 *
 * The server never writes code into the page: each table leaves its
 * configuration as JSON in a <script type="application/json"> and this file
 * builds the ObjectCRUD from it, choosing every renderer here. Everything a
 * row carries comes from users, and DataTables, ObjectCRUD and the delete
 * modal put what they are given into the page as HTML, so every renderer
 * escapes; the titles and icons already arrive escaped from the server.
 *
 * Facets (GTFacets, djgentelella.datasources) share a GTDataSourceState with
 * the table they filter (`target`): a change of facet reloads the table with
 * the facets as filters (`gtfilters`), and the table's search box goes
 * into the facets' counts. A chart bound to the same panel (its `facets`
 * prop: `data-gtfacets-target`) is drawn again with the same filters; the
 * table's search box does not reach it.
 *
 * Preview pages (the editor) have no endpoints: their charts draw the sample
 * data they carry.
 */
(function () {
    'use strict';

    var ENTITIES = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'};

    function escape(value) {
        return (value === null || value === undefined ? '' : String(value))
            .replace(/[&<>"']/g, function (c) { return ENTITIES[c]; });
    }

    function readJSON(id) {
        var element = document.getElementById(id);
        return element ? JSON.parse(element.textContent) : null;
    }

    function relationText(obj) {
        if (obj === null || obj === undefined) { return null; }
        if (typeof obj !== 'object') { return escape(obj); }
        return escape(obj.text !== undefined ? obj.text : obj.display_name);
    }

    function safeHref(url) {
        // Only links within the site or to http(s); never javascript:.
        url = String(url || '');
        return /^(https?:\/\/|\/)/i.test(url) ? url : '';
    }

    /* The DataTables renderer of a column, by the kind of its model field. */
    function renderer(column) {
        var kind = column.kind;
        if (kind === 'fk' || kind === 'o2o') {
            return function (data, type) {
                if (type !== 'display') { return data && typeof data === 'object' ? data.text : data; }
                var text = relationText(data);
                return text === null ? '---' : text;
            };
        }
        if (kind === 'm2m') {
            return function (data, type) {
                var items = data === null || data === undefined ? [] : (Array.isArray(data) ? data : [data]);
                var texts = items.map(relationText).filter(function (t) { return t !== null; });
                if (type !== 'display') { return texts.join(', '); }
                return texts.length ? texts.join('<br>') : '---';
            };
        }
        if (kind === 'boolean' || kind === 'nullboolean') {
            return function (data, type) {
                if (type !== 'display') { return data; }
                if (data === null || data === undefined) { return '---'; }
                return yesnoprint(data);
            };
        }
        if (kind === 'choices') {
            var labels = {};
            (column.choices || []).forEach(function (c) { labels[String(c[0])] = c[1]; });
            // The labels arrive escaped; an unknown value is escaped here.
            return function (data, type) {
                if (data === null || data === undefined) { return ''; }
                return String(data) in labels ? labels[String(data)] : escape(data);
            };
        }
        if (kind === 'file' || kind === 'image') {
            return function (data, type) {
                var href = safeHref(data);
                if (type !== 'display' || !href) { return type === 'display' ? '' : data; }
                return '<a href="' + escape(href) + '" target="_blank" rel="noopener" ' +
                    'class="btn btn-xs btn-success">' + escape(gettext('Download')) + '</a>';
            };
        }
        return $.fn.dataTable.render.text();
    }

    function columns(config) {
        var result = [{data: 'id', name: 'id', title: escape(gettext('Id')), type: 'readonly',
                       visible: false}];
        config.columns.forEach(function (column) {
            var item = {data: column.data, name: column.name, title: column.title,
                        type: column.type, visible: true, render: renderer(column)};
            if (column.kind === 'date') { item.dateformat = document.date_format; }
            if (column.kind === 'datetime') { item.dateformat = document.datetime_format; }
            if (column.choices) { item.choices = column.choices; }
            if (column.url) { item.url = column.url; }
            if (column.multiple) { item.multiple = true; }
            if (column.kind === 'm2m') { item.orderable = false; }
            result.push(item);
        });
        result.push({data: 'actions', name: 'actions', title: escape(gettext('Actions')),
                     type: 'actions', visible: true});
        return result;
    }

    function rowLinks(config) {
        return config.row_links.map(function (link) {
            return {
                name: link.name, title: link.title, i_class: link.i_class, link: true,
                url_fn: function (data) {
                    return link.url.split(link.placeholder).join(encodeURIComponent(data.id));
                }
            };
        });
    }

    /* Tables and the facet states that filter them, by node id; either side
       may come first. */
    var tables = {};

    function table(id) {
        if (!(id in tables)) { tables[id] = {crud: null, states: [], charts: []}; }
        return tables[id];
    }

    function linkState(id, state) {
        var entry = table(id);
        if (entry.states.indexOf(state) >= 0) { return; }
        entry.states.push(state);
        state.subscribe(function () {
            if (entry.crud && entry.crud.datatable) { entry.crud.datatable.ajax.reload(); }
            entry.charts.forEach(function (chart) { reloadChart(chart, facetFilters(id)); });
        });
    }

    /* Draw a chart again with `filters`; only the answer to the last request
       is drawn, whatever order they come back in. */
    function reloadChart(element, filters) {
        var graph = element.querySelector('.gentelella_graph');
        var canvas = graph && graph.querySelector('canvas');
        if (!canvas || typeof Chart === 'undefined') { return; }
        var params = {};
        if (filters.length) { params.gtfilters = JSON.stringify(filters); }
        var seq = (element.gtchartSeq || 0) + 1;
        element.gtchartSeq = seq;
        element.setAttribute('data-gtloading', 'true');
        $.ajax({url: graph.getAttribute('data-url'), type: 'GET', dataType: 'json',
                data: params})
            .done(function (result) {
                if (seq !== element.gtchartSeq) { return; }
                var chart = Chart.getChart(canvas);
                if (chart && result.data) {
                    chart.data.labels = result.data.labels;
                    chart.data.datasets = result.data.datasets;
                    chart.update();
                } else if (!chart) {
                    $(graph).data('chartInstance', new Chart(canvas, result));
                }
            })
            .always(function () {
                if (seq === element.gtchartSeq) { element.removeAttribute('data-gtloading'); }
            });
    }

    function initChart(element) {
        var target = element.getAttribute('data-gtfacets-target');
        if (target) { table(target).charts.push(element); }
    }

    function facetFilters(id) {
        var filters = [];
        table(id).states.forEach(function (state) {
            Object.keys(state.facetFilters).forEach(function (name) {
                filters.push(state.facetFilters[name]);
            });
        });
        return filters;
    }

    function initTable(element) {
        var config = readJSON(element.getAttribute('data-gtconfig'));
        if (!config) { return; }
        var id = config.id;
        var entry = table(id);
        var options = {
            urls: config.urls,
            datatable_element: '#' + id + '_table',
            modal_ids: config.modal_ids,
            actions: {table_actions: [], object_actions: rowLinks(config),
                      title: gettext('Actions'), className: 'no-export-col'},
            datatable_inits: {
                columns: columns(config),
                addfilter: true,
                events: {
                    filter: function (data) {
                        var filters = facetFilters(id);
                        if (filters.length) { data.gtfilters = JSON.stringify(filters); }
                        entry.states.forEach(function (state) { state.setSearch(data.search || ''); });
                        return data;
                    }
                }
            },
            add_filter: true,
            relation_render: {},
            delete_display: function (data) { return escape(data[config.delete_display]); }
        };
        config.columns.forEach(function (column) {
            if (column.kind === 'fk' || column.kind === 'o2o') { options.relation_render[column.name] = 'text'; }
        });
        entry.crud = ObjectCRUD(id, options);
        entry.crud.init();
    }

    function initFacets(element) {
        var $element = $(element);
        var state = gt_datasource_state($element.data('url'), $element.data('group'));
        linkState(String($element.data('target')), state);
        new GTFacets(element);
    }

    function initSample(element) {
        var sample = readJSON(element.getAttribute('data-gtsample'));
        var canvas = element.querySelector('canvas');
        if (!sample || !canvas || typeof Chart === 'undefined') { return; }
        var circular = sample.type === 'pie' || sample.type === 'doughnut';
        new Chart(canvas, {
            type: sample.type,
            data: {labels: sample.labels, datasets: [{label: '', data: sample.values}]},
            options: {responsive: true, maintainAspectRatio: !circular,
                      indexAxis: sample.horizontal ? 'y' : 'x'}
        });
    }

    function init() {
        document.querySelectorAll('.gtdesign-chart[data-gtfacets-target]').forEach(initChart);
        document.querySelectorAll('.gtdesign-facets').forEach(initFacets);
        document.querySelectorAll('.gtdesign-table[data-gtconfig]').forEach(initTable);
        document.querySelectorAll('.gtdesign-chart-sample').forEach(initSample);
    }

    window.gtdesign_escape = escape;
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
