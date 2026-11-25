/* The tree, timeline and metrics region components of djgentelella.designs
 * in the browser (djgentelella/designs/tree_timeline_metrics.py).
 *
 * Each node leaves its configuration as JSON in a
 * <script type="application/json" id="<node>_gtconfig">. Row data is
 * written with textContent, never as HTML; the only HTML taken from the
 * server is the metric cards, which a Django template rendered and escaped.
 *
 * - tree: one level per request (`?parent=<key>&offset=`) or, with
 *   `load: "full"`, every row at once as a flat pre-order list. A node that
 *   is already one of its own ancestors is never opened, so a cycle in the
 *   data cannot loop here either;
 * - timeline: newest first, "Load older" asks for the next page with the
 *   cursor the server gave;
 * - metrics: the cards are reloaded when the page's facets change.
 *
 * Facets: a component joins the GTDataSourceState of its group
 * (`gtdesign:<node id>`), the one a facets panel writes into, and reloads
 * with the panel's parameter document: over a data source the state of its
 * API, over a model that of the panel's own endpoint (the data-url of the
 * panel of the group). No library is needed.
 */
(function () {
    'use strict';

    function readJSON(id) {
        var element = document.getElementById(id);
        return element ? JSON.parse(element.textContent) : null;
    }

    function status(region, text) {
        var element = region.querySelector('[role="status"]');
        if (element) { element.textContent = text || ''; }
    }

    /* The URL of the data source state of `config`: its data source API or,
       over a model, the endpoint of the facets panel of its group on the
       page (that panel's data-url). */
    function facetUrl(config) {
        if (config.datasource_url) { return config.datasource_url; }
        if (!config.group) { return null; }
        var panels = document.querySelectorAll('.gtdesign-facets[data-group]');
        for (var i = 0; i < panels.length; i++) {
            if (panels[i].getAttribute('data-group') === config.group) {
                return panels[i].getAttribute('data-url');
            }
        }
        return null;
    }

    function facetState(config, reload) {
        var url = facetUrl(config);
        if (!url || typeof gt_datasource_state !== 'function') { return null; }
        var state = gt_datasource_state(url, config.group);
        state.subscribe(reload);
        return state;
    }

    function paramsOf(state) {
        return state ? state.params() : {};
    }

    function query(url, values) {
        var qs = new URLSearchParams(values).toString();
        return url + (url.indexOf('?') >= 0 ? '&' : '?') + qs;
    }

    function getJSON(url) {
        return fetch(url, {credentials: 'same-origin', headers: {'Accept': 'application/json'}})
            .then(function (response) {
                if (!response.ok) { throw new Error(response.status); }
                return response.json();
            });
    }

    function make(tag, className, text) {
        var element = document.createElement(tag);
        if (className) { element.className = className; }
        if (text !== undefined && text !== null && text !== '') { element.textContent = text; }
        return element;
    }

    function bump(element) {
        element.dataset.loaded = String(Number(element.dataset.loaded || 0) + 1);
    }

    /* The title of a row: a link to its row link, or plain text. */
    function titleOf(item, className) {
        var title;
        if (item.url) {
            title = make('a', className, item.title);
            title.href = item.url;
        } else {
            title = make('span', className, item.title);
        }
        return title;
    }

    function fieldsText(fields) {
        return (fields || []).filter(function (item) { return item.value !== ''; })
            .map(function (item) { return item.label + ': ' + item.value; }).join(' · ');
    }

    // -- tree ----------------------------------------------------------------------

    function initTree(region, config) {
        var root = region.querySelector('.gttree');
        var state = null;
        var generation = 0;

        function notes(data) {
            var texts = [];
            if (data.orphans) {
                texts.push(interpolate(gettext('%s rows whose parent is not shown are at the root.'), [data.orphans]));
            }
            if (data.cycles) {
                texts.push(interpolate(gettext('%s cycles in the parents: one row of each is at the root.'), [data.cycles]));
            }
            if (data.checked === false) {
                texts.push(gettext('Too many rows to look for cycles in the parents.'));
            }
            if (data.truncated) {
                texts.push(interpolate(gettext('Showing the first %s rows.'), [config.limit]));
            }
            return texts.join(' ');
        }

        /* One <li role="treeitem">; `ancestors` are the keys above it. */
        function nodeItem(node, ancestors, depth) {
            var li = make('li');
            li.setAttribute('role', 'treeitem');
            li.dataset.key = node.key;
            li.setAttribute('aria-level', String(depth + 1));
            var row = make('div', 'gttree-row');
            var toggle = make('button', 'gttree-toggle');
            toggle.type = 'button';
            var loop = ancestors.indexOf(node.key) >= 0;
            var openable = node.children && !loop;
            toggle.disabled = !openable;
            toggle.setAttribute('aria-label', gettext('Open'));
            toggle.appendChild(make('i', 'fa fa-caret-right'));
            row.appendChild(toggle);
            var icon = make('i', node.icon || (node.children ? 'fa fa-folder-o' : 'fa fa-file-o'));
            icon.setAttribute('aria-hidden', 'true');
            row.appendChild(icon);
            row.appendChild(titleOf(node, 'gttree-title'));
            if (node.subtitle) { row.appendChild(make('small', 'text-muted', node.subtitle)); }
            var fields = fieldsText(node.fields);
            if (fields) { row.appendChild(make('span', 'gttree-fields', fields)); }
            if (node.orphan) {
                var orphan = make('span', 'badge bg-warning text-dark', gettext('parent not shown'));
                row.appendChild(orphan);
            }
            if (node.cycle || loop) {
                row.appendChild(make('span', 'badge bg-danger', gettext('cycle')));
            }
            li.appendChild(row);
            if (openable) {
                li.setAttribute('aria-expanded', 'false');
                toggle.addEventListener('click', function () { flip(li, node, ancestors.concat([node.key]), depth); });
            }
            return li;
        }

        function setOpen(li, open) {
            li.setAttribute('aria-expanded', open ? 'true' : 'false');
            var caret = li.querySelector(':scope > .gttree-row .gttree-toggle i');
            caret.className = open ? 'fa fa-caret-down' : 'fa fa-caret-right';
            var group = li.querySelector(':scope > ul');
            if (group) { group.hidden = !open; }
        }

        function flip(li, node, ancestors, depth) {
            var open = li.getAttribute('aria-expanded') !== 'true';
            var group = li.querySelector(':scope > ul');
            if (open && !group && config.load !== 'full') {
                group = make('ul');
                group.setAttribute('role', 'group');
                li.appendChild(group);
                level(group, node.key, 0, ancestors, depth + 1);
            }
            setOpen(li, open);
        }

        /* Lazy: one page of the children of `parent` (null: the roots). */
        function level(list, parent, offset, ancestors, depth) {
            var mine = generation;
            var values = {params: JSON.stringify(paramsOf(state)), offset: offset};
            if (parent !== null) { values.parent = parent; }
            list.setAttribute('aria-busy', 'true');
            return getJSON(query(config.url, values)).then(function (data) {
                if (mine !== generation) { return; }
                list.removeAttribute('aria-busy');
                data.nodes.forEach(function (node) { list.appendChild(nodeItem(node, ancestors, depth)); });
                if (data.next_offset !== null && data.next_offset !== undefined) {
                    var more = make('button', 'btn btn-sm btn-link gttree-more', gettext('More'));
                    more.type = 'button';
                    more.addEventListener('click', function () {
                        more.remove();
                        level(list, parent, data.next_offset, ancestors, depth);
                    });
                    list.appendChild(make('li')).appendChild(more);
                }
                if (parent === null) { status(region, notes(data)); }
                bump(root);
            }).catch(function () {
                list.removeAttribute('aria-busy');
                status(region, gettext('The tree could not be loaded.'));
            });
        }

        /* Full: the flat pre-order list, each node under its `parent`. */
        function full() {
            var mine = generation;
            return getJSON(query(config.url, {params: JSON.stringify(paramsOf(state))})).then(function (data) {
                if (mine !== generation) { return; }
                var lists = {}, items = {}, paths = {};
                data.nodes.forEach(function (node) {
                    var parentList = root, path = [];
                    if (node.parent !== null && node.parent !== undefined && items[node.parent]) {
                        if (!lists[node.parent]) {
                            lists[node.parent] = make('ul');
                            lists[node.parent].setAttribute('role', 'group');
                            items[node.parent].appendChild(lists[node.parent]);
                        }
                        parentList = lists[node.parent];
                        path = paths[node.parent].concat([node.parent]);
                    }
                    var li = nodeItem(node, path, node.depth || 0);
                    parentList.appendChild(li);
                    items[node.key] = li;
                    paths[node.key] = path;
                });
                Object.keys(lists).forEach(function (key) {
                    setOpen(items[key], (paths[key].length + 1) <= config.expand);
                });
                status(region, notes(data));
                bump(root);
            }).catch(function () {
                status(region, gettext('The tree could not be loaded.'));
            });
        }

        function reload() {
            generation += 1;
            root.textContent = '';
            if (config.load === 'full') { full(); } else { level(root, null, 0, [], 0); }
        }

        state = facetState(config, reload);
        reload();
        region.gtregion = {reload: reload};
    }

    // -- timeline ------------------------------------------------------------------

    function initTimeline(region, config) {
        var list = region.querySelector('.gttimeline');
        var more = region.querySelector('.gttimeline-more');
        var state = null;
        var cursor = null;
        var lastGroup = null;
        var generation = 0;

        function item(entry) {
            if (entry.group && entry.group !== lastGroup) {
                list.appendChild(make('li', 'gttimeline-group', entry.group));
                lastGroup = entry.group;
            }
            var li = make('li', 'gttimeline-item');
            li.dataset.id = entry.id;
            var dot = make('span', 'gttimeline-dot');
            if (entry.color) { dot.style.backgroundColor = entry.color; }
            li.appendChild(dot);
            var when = make('time', 'gttimeline-when', entry.until ? entry.when + ' – ' + entry.until : entry.when);
            if (entry.start) { when.dateTime = entry.start; }
            li.appendChild(when);
            var head = make('div');
            head.appendChild(titleOf(entry, 'gttimeline-title fw-semibold'));
            if (entry.subtitle) {
                head.appendChild(document.createTextNode(' '));
                head.appendChild(make('small', 'text-muted', entry.subtitle));
            }
            li.appendChild(head);
            if (entry.description) { li.appendChild(make('p', 'gttimeline-description', entry.description)); }
            var fields = fieldsText(entry.fields);
            if (fields) { li.appendChild(make('div', 'gttimeline-when', fields)); }
            return li;
        }

        function page() {
            var mine = generation;
            var values = {params: JSON.stringify(paramsOf(state))};
            if (cursor) { values.cursor = cursor; }
            more.disabled = true;
            list.setAttribute('aria-busy', 'true');
            return getJSON(query(config.url, values)).then(function (data) {
                if (mine !== generation) { return; }
                list.removeAttribute('aria-busy');
                data.items.forEach(function (entry) { list.appendChild(item(entry)); });
                cursor = data.next;
                more.disabled = false;
                more.classList.toggle('d-none', !cursor);
                if (!list.children.length) { status(region, gettext('Nothing to show.')); } else { status(region, ''); }
                bump(list);
            }).catch(function () {
                list.removeAttribute('aria-busy');
                more.disabled = false;
                status(region, gettext('The timeline could not be loaded.'));
            });
        }

        function reload() {
            generation += 1;
            cursor = null;
            lastGroup = null;
            list.textContent = '';
            more.classList.add('d-none');
            page();
        }

        more.addEventListener('click', page);
        state = facetState(config, reload);
        reload();
        region.gtregion = {reload: reload, more: page};
    }

    // -- metrics -------------------------------------------------------------------

    function initMetrics(region, config) {
        var cards = region.querySelector('.gtmetrics-cards');
        var request = 0;

        function reload() {
            var mine = ++request;
            cards.setAttribute('aria-busy', 'true');
            getJSON(query(config.url, {params: JSON.stringify(paramsOf(state))})).then(function (data) {
                if (mine !== request) { return; }
                cards.removeAttribute('aria-busy');
                // Rendered and escaped by the server's template.
                cards.innerHTML = data.html;
                status(region, '');
                bump(cards);
            }).catch(function () {
                cards.removeAttribute('aria-busy');
                status(region, gettext('The metrics could not be computed.'));
            });
        }

        // The page came with the cards: only the facets reload them.
        var state = facetState(config, reload);
        region.gtregion = {reload: reload};
    }

    var INIT = {tree: initTree, timeline: initTimeline, metrics: initMetrics};

    function init() {
        document.querySelectorAll('.gtdesign-region[data-gtconfig]').forEach(function (region) {
            if (region.gtregion) { return; }
            var config = readJSON(region.getAttribute('data-gtconfig'));
            if (config && INIT[config.type]) { INIT[config.type](region, config); }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
