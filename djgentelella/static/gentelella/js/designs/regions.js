/* The region components of djgentelella.designs in the browser: cards,
 * calendar and map (djgentelella/designs/regions.py).
 *
 * Each node leaves its configuration as JSON in a
 * <script type="application/json" id="<node>_gtconfig">; nothing here builds
 * HTML out of row data by concatenation:
 *
 * - cards are a CardList (api_list.js), the client of ListAreaViewset: the
 *   server sends the rows and a Squirrelly template that escapes them;
 * - the calendar is FullCalendar, fed by a function that asks the endpoint
 *   for the visible range only; FullCalendar writes titles as text;
 * - the map is createGTMap (maplib.js): the popups are HTML the server
 *   rendered and escaped; with `bbox` the points of the visible box are
 *   asked again when the map moves.
 *
 * Facets: a component joins the GTDataSourceState of its group
 * (`gtdesign:<node id>`), the one the facets panel writes its filters into,
 * and reloads with the panel's parameter document. Over a data source the
 * state is that of its API; over a model, that of the panel's own endpoint
 * (the data-url of the panel of the group).
 *
 * FullCalendar and Leaflet.markercluster are loaded here when the page lacks
 * them (only the readonly widgets and `use_maps` bring them).
 */
(function () {
    'use strict';

    function readJSON(id) {
        var element = document.getElementById(id);
        return element ? JSON.parse(element.textContent) : null;
    }

    var loading = {};

    /* Load a script or a stylesheet once; resolves when it is there. */
    function load(url) {
        if (!(url in loading)) {
            loading[url] = new Promise(function (resolve, reject) {
                var element;
                if (/\.css(\?|$)/.test(url)) {
                    element = document.createElement('link');
                    element.rel = 'stylesheet';
                    element.href = url;
                } else {
                    element = document.createElement('script');
                    element.src = url;
                }
                element.onload = resolve;
                element.onerror = reject;
                document.head.appendChild(element);
            });
        }
        return loading[url];
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

    /* The data source state shared with a facets panel, or null. */
    function facetState(config, reload) {
        var url = facetUrl(config);
        if (!url || typeof gt_datasource_state !== 'function') { return null; }
        var state = gt_datasource_state(url, config.group);
        state.subscribe(reload);
        return state;
    }

    function paramsOf(state, search) {
        var params = state ? state.params() : {};
        if (search && !state) { params.search = search; }
        return params;
    }

    function query(url, values) {
        var qs = new URLSearchParams(values).toString();
        return url + (url.indexOf('?') >= 0 ? '&' : '?') + qs;
    }

    // -- cards ---------------------------------------------------------------------

    var GTDesignCards = (typeof CardList === 'undefined') ? null : class extends CardList {
        constructor(containerId, config) {
            // CardList fetches in its constructor: the parameters must be
            // there before super() runs, hence the static stash.
            GTDesignCards.pending = config;
            super(containerId, config.url, {});
        }

        fetchData() {
            if (GTDesignCards.pending) {
                this.config = GTDesignCards.pending;
                this.page_size = this.config.page_size;
                this.search = '';
                GTDesignCards.pending = null;
            }
            this.filters = {params: JSON.stringify(paramsOf(this.state, this.search))};
            this.container.setAttribute('aria-busy', 'true');
            var self = this;
            return super.fetchData().then(function () {
                self.container.removeAttribute('aria-busy');
                self.container.dataset.loaded = String(Number(self.container.dataset.loaded || 0) + 1);
            });
        }

        getFilters() { this.page = 1; this.fetchData(); }

        doPagination() {
            var self = this;
            this.container.querySelectorAll('.pagination a').forEach(function (link) {
                link.onclick = function (event) {
                    event.preventDefault();
                    self.page = link.dataset.page;
                    self.fetchData();
                };
            });
        }
    };

    function initCards(region, config) {
        if (!GTDesignCards) { status(region, gettext('The cards could not be loaded.')); return; }
        var cards = new GTDesignCards(config.id + '_cards', config);
        cards.state = facetState(config, function () { cards.getFilters(); });
        if (cards.state) { cards.getFilters(); }
        var box = region.querySelector('.gtcards-search');
        if (box) {
            var timer = null;
            box.addEventListener('input', function () {
                clearTimeout(timer);
                timer = setTimeout(function () {
                    cards.search = box.value;
                    if (cards.state) { cards.state.setSearch(box.value); }
                    cards.getFilters();
                }, 300);
            });
        }
        region.gtregion = cards;
    }

    // -- calendar ------------------------------------------------------------------

    function initCalendar(region, config) {
        var ready = typeof FullCalendar !== 'undefined' ? Promise.resolve() : load(config.fullcalendar);
        if (config.locales) {
            // The locales register themselves in FullCalendar.globalLocales:
            // after the library, and only on a page in another language.
            ready = ready.then(function () {
                var known = FullCalendar.globalLocales || [];
                var code = config.locale.split('-')[0];
                if (known.some(function (item) { return item.code === config.locale || item.code === code; })) { return null; }
                return load(config.locales).catch(function () { return null; });
            });
        }
        ready.then(function () {
            var element = region.querySelector('.gtcalendar');
            var state = null;
            var options = {
                initialView: config.initial_view,
                headerToolbar: {left: 'prev,next today', center: 'title',
                                right: 'dayGridMonth,timeGridWeek,listMonth'},
                height: 'auto',
                events: function (info, success, failure) {
                    var url = query(config.url, {start: info.startStr, end: info.endStr,
                                                 params: JSON.stringify(paramsOf(state))});
                    fetch(url, {credentials: 'same-origin', headers: {'Accept': 'application/json'}})
                        .then(function (response) {
                            if (!response.ok) { throw new Error(response.status); }
                            return response.json();
                        })
                        .then(function (data) {
                            status(region, data.truncated ? interpolate(
                                gettext('Showing the first %s events of this range.'), [config.limit]) : '');
                            element.dataset.loaded = String(Number(element.dataset.loaded || 0) + 1);
                            success(data.events);
                        })
                        .catch(function (error) {
                            status(region, gettext('The events could not be loaded.'));
                            failure(error);
                        });
                }
            };
            if (config.locale) { options.locale = config.locale; }
            var calendar = new FullCalendar.Calendar(element, options);
            state = facetState(config, function () { calendar.refetchEvents(); });
            calendar.render();
            region.gtregion = calendar;
        }).catch(function () {
            status(region, gettext('The calendar could not be loaded.'));
        });
    }

    // -- map -----------------------------------------------------------------------

    function initMap(region, config) {
        var ready = Promise.resolve();
        if (config.cluster && typeof L !== 'undefined' && typeof L.markerClusterGroup !== 'function') {
            ready = Promise.all(config.markercluster.map(load));
        }
        ready.catch(function () { /* drawn without clustering */ }).then(function () {
            var element = region.querySelector('.gtmap');
            var options = {};
            if (config.center) { options.center = config.center; options.zoom = config.zoom; }
            var engine = createGTMap(element, options);
            if (!engine) { return; }
            var state = null;
            var first = true;
            var request = 0;

            function draw(withBox) {
                var values = {params: JSON.stringify(paramsOf(state))};
                if (withBox) {
                    var bounds = engine.map.getBounds();
                    values.bbox = [bounds.getWest(), bounds.getSouth(),
                                   bounds.getEast(), bounds.getNorth()].map(function (n) {
                        return n.toFixed(6);
                    }).join(',');
                }
                var mine = ++request;
                fetch(query(config.url, values), {credentials: 'same-origin',
                                                  headers: {'Accept': 'application/json'}})
                    .then(function (response) {
                        if (!response.ok) { throw new Error(response.status); }
                        return response.json();
                    })
                    .then(function (payload) {
                        if (mine !== request) { return; }
                        if (config.center && first) { payload.fit_bounds = false; }
                        engine.setData(payload);
                        first = false;
                        status(region, payload.truncated ? interpolate(
                            gettext('Showing the first %s points: zoom in to see the others.'),
                            [config.limit]) : '');
                        element.dataset.loaded = String(Number(element.dataset.loaded || 0) + 1);
                    })
                    .catch(function () { status(region, gettext('The points could not be loaded.')); });
            }

            state = facetState(config, function () { draw(config.bbox && !first); });
            draw(false);
            if (config.bbox) {
                var timer = null;
                engine.map.on('moveend', function () {
                    if (engine._programmaticMove || first) { return; }
                    clearTimeout(timer);
                    timer = setTimeout(function () { draw(true); }, 250);
                });
            }
            region.gtregion = engine;
        });
    }

    var INIT = {cards: initCards, calendar: initCalendar, map: initMap};

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
