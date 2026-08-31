// Shared Leaflet engine for every map widget in the library.
//
// Consumers: mappoint.js (the MapPointInput form widget) and map.js (the DJMap
// dashboard widget). Both go through createGTMap so there is a single place
// that knows how to build a map, how to tear one down, and how to work around
// the two Leaflet integration problems this project has (see below).
//
// Load order: createbasejs.py lists this file in `basefiles`, after mappoint.js
// needs it and -- more surprisingly -- after the whole `jquery_plugins` block
// that contains map.js. That works only because everything here is a hoisted
// function declaration and nothing calls it until the page is ready. Keep it
// that way: turn any of these into a `var f = function(){}` and map.js breaks,
// because its half of base.js is concatenated first.

// Overridable by a project before boot, the way document.chartcallbacks is.
document.gt_map_defaults = {
    tileUrl: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    tileAttribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    center: [0, 0],
    zoom: 13,
    minZoom: 2,
    maxZoom: 19,
    // 6 decimals is ~11 cm, well past what any consumer-grade GPS resolves.
    precision: 6,
    geocoderUrl: 'https://nominatim.openstreetmap.org/search'
};

// Live engines by container id. A container re-render (api_list.js rebuilds
// innerHTML and re-runs gt_find_initialize_from_dom, a modal reopened, a
// formset row cloned) calls the widget initialiser again for a brand new node.
// Without this the old engine is unreachable through the DOM, Leaflet throws
// "Map container is already initialized" on the reused id, and the abandoned
// map keeps requesting tiles and holding its listeners forever.
var _gt_maps = {};

function gt_map_leaflet_ok() {
    if (typeof L === 'undefined') {
        console.error('djgentelella maps: Leaflet is not loaded. Check that ' +
                      'loaddevstatic downloaded vendors/leaflet and that the ' +
                      'maps bundle is in gentelella/statics/javascript.html.');
        return false;
    }
    // storymapjs embeds Leaflet 0.7.7 and assigns it to window.L. If its bundle
    // is emitted after ours, window.L is silently downgraded: the plugins
    // patched the object that got replaced, so L.markerClusterGroup and
    // L.heatLayer vanish and every map fails against a 0.7 API.
    if (!L.version || L.version.charAt(0) !== '1') {
        console.error('djgentelella maps: expected Leaflet 1.x but found ' +
                      L.version + '. Something (storymapjs bundles 0.7.7) ' +
                      'overwrote window.L. The maps bundle must load after ' +
                      'djgentelella.readonly.vendors.min.js.');
        return false;
    }
    return true;
}

// Leaflet finds its marker images by reading the computed background-image of
// .leaflet-default-icon-path and stripping marker-icon.png off the end. The
// urlreplace transformer in pylpfile.py rewrites that url() into a base64 data
// URI, so in compressed mode the guess returns garbage and every default pin
// 404s. javascript.html hands us the real static URLs instead -- which also
// keeps ManifestStaticFilesStorage's per-file hashing working.
function gt_map_fix_icon_path() {
    if (!document.gt_leaflet_images) return;
    L.Icon.Default.mergeOptions(document.gt_leaflet_images);
}

// "9.9327,-84.0875" -> {lat, lng}, or null. Deliberately strict: anything that
// is not exactly two finite numbers in range is a parse failure, so the widget
// can tell the user what is wrong instead of dropping a marker in the ocean.
function gt_parse_latlng(value) {
    if (value === null || value === undefined) return null;
    var parts = String(value).trim().split(',');
    if (parts.length !== 2) return null;
    var lat = parseFloat(parts[0]);
    var lng = parseFloat(parts[1]);
    if (!isFinite(lat) || !isFinite(lng)) return null;
    if (lat < -90 || lat > 90) return null;
    if (lng < -180 || lng > 180) return null;
    return {lat: lat, lng: lng};
}

function gt_format_latlng(lat, lng, precision) {
    if (precision === undefined || precision === null) {
        precision = document.gt_map_defaults.precision;
    }
    return Number(lat).toFixed(precision) + ',' + Number(lng).toFixed(precision);
}

// Lifted from the private resolveValue in chart.js so map filters accept the
// exact same syntax chart users already know: '{fnName}' calls a global
// function, '#id'/'.class' read a live element, anything else is a literal.
function gt_resolve_value(value) {
    if (typeof value !== 'string') return value;

    if (value.startsWith('{') && value.endsWith('}')) {
        var funcName = value.slice(1, -1);
        if (typeof window[funcName] === 'function') {
            return window[funcName]();
        }
    }
    if (value.startsWith('#') || value.startsWith('.')) {
        var el = $(value).first();
        if (el.length) {
            // chart.js does `el.val() || el.text()`, which breaks on a form
            // control whose selected value is legitimately empty: an "All"
            // option with value="" falls through and sends the concatenated
            // text of every option as the filter. For a form control val() is
            // authoritative, empty or not.
            if (el.is('input, select, textarea')) return el.val();
            return el.text();
        }
    }
    return value;
}

// data-* -> config, the shape voiceBaseConfig(el) has in voiceprogressive.js.
function gt_map_config_from_data(el) {
    var d = document.gt_map_defaults;
    var data = el.data();
    var cfg = {
        tileUrl: data.tileUrl || d.tileUrl,
        tileAttribution: data.tileAttribution || d.tileAttribution,
        zoom: data.zoom !== undefined ? parseInt(data.zoom, 10) : d.zoom,
        minZoom: data.minZoom !== undefined ? parseInt(data.minZoom, 10) : d.minZoom,
        maxZoom: data.maxZoom !== undefined ? parseInt(data.maxZoom, 10) : d.maxZoom,
        geocoderUrl: data.geocoderUrl !== undefined ? data.geocoderUrl : d.geocoderUrl,
        center: d.center
    };
    var center = gt_parse_latlng(data.center);
    if (center) cfg.center = [center.lat, center.lng];
    return cfg;
}

// Nominatim. Kept behind an explicit opt-in by the widgets: the OSM usage
// policy forbids heavy automated use, wants an identifying Referer and caps
// callers at 1 req/s, so a shared IP gets banned if this fires on keystrokes.
// geocoderUrl lets a project point at its own Nominatim/Photon instance.
function gt_map_geocode(query, opts) {
    opts = opts || {};
    var url = opts.geocoderUrl || document.gt_map_defaults.geocoderUrl;
    if (!url || !query) return Promise.resolve([]);
    var params = new URLSearchParams({
        q: query,
        format: 'json',
        limit: opts.limit || 5
    });
    return fetch(url + '?' + params.toString(), {signal: opts.signal})
        .then(function (r) {
            if (!r.ok) throw new Error('geocoder returned ' + r.status);
            return r.json();
        })
        .then(function (data) {
            return (data || []).map(function (item) {
                return {
                    lat: parseFloat(item.lat),
                    lng: parseFloat(item.lon),
                    label: item.display_name,
                    boundingbox: item.boundingbox
                };
            }).filter(function (p) { return isFinite(p.lat) && isFinite(p.lng); });
        });
}

// Bootstrap hides tab/modal/collapse panes with display:none. A Leaflet map
// built inside one measures 0x0 and renders as a grey box that never recovers
// on its own, so every live engine is resized when a pane is shown. Registered
// once for all maps rather than per engine.
$(document).on('shown.bs.tab shown.bs.modal shown.bs.collapse', function () {
    Object.keys(_gt_maps).forEach(function (id) {
        _gt_maps[id].invalidateSize();
    });
});

function gt_map_show_error(container, message) {
    $(container).html($('<div class="gt-map-error"></div>').text(message));
}

/**
 * Build a map inside `container` (a DOM element with a non-empty id).
 * Returns the engine, or null when Leaflet is unusable.
 */
function createGTMap(container, opts) {
    opts = opts || {};
    var id = container.id;

    if (!gt_map_leaflet_ok()) {
        gt_map_show_error(container, 'Leaflet is not available');
        return null;
    }
    gt_map_fix_icon_path();

    // Replace rather than stack: see the _gt_maps comment.
    if (id && _gt_maps[id]) {
        _gt_maps[id].destroy();
        delete _gt_maps[id];
    }

    var cfg = $.extend({}, document.gt_map_defaults, opts);
    var map = L.map(container, {
        center: cfg.center,
        zoom: cfg.zoom,
        minZoom: cfg.minZoom,
        maxZoom: cfg.maxZoom,
        scrollWheelZoom: cfg.scrollWheelZoom !== false
    });
    L.tileLayer(cfg.tileUrl, {
        attribution: cfg.tileAttribution,
        maxZoom: cfg.maxZoom
    }).addTo(map);

    var engine = {
        map: map,
        options: cfg,
        marker: null,
        layers: {},
        heatLayer: null,
        control: null,
        // Set while the engine itself is moving the map, so the optional
        // refetch-on-move handler does not react to its own fitBounds and
        // spin in a fetch -> fit -> moveend -> fetch loop.
        _programmaticMove: false
    };

    engine._moveProgrammatically = function (fn) {
        engine._programmaticMove = true;
        try {
            fn();
        } finally {
            // moveend fires asynchronously after the animation.
            setTimeout(function () { engine._programmaticMove = false; }, 0);
        }
    };

    engine.invalidateSize = function () {
        map.invalidateSize();
        return engine;
    };

    // --- single point mode (MapPointInput) ------------------------------
    engine.setPoint = function (latlng, panTo) {
        var point = L.latLng(latlng);
        if (engine.marker) {
            engine.marker.setLatLng(point);
        } else {
            engine.marker = L.marker(point, {draggable: !cfg.readonly}).addTo(map);
            if (cfg.onMarkerDrag) {
                engine.marker.on('dragend', function () {
                    cfg.onMarkerDrag(engine.marker.getLatLng());
                });
            }
        }
        if (panTo !== false) {
            engine._moveProgrammatically(function () { map.panTo(point); });
        }
        return engine;
    };

    engine.getPoint = function () {
        return engine.marker ? engine.marker.getLatLng() : null;
    };

    engine.clear = function () {
        if (engine.marker) {
            map.removeLayer(engine.marker);
            engine.marker = null;
        }
        if (engine.accuracyCircle) {
            map.removeLayer(engine.accuracyCircle);
            engine.accuracyCircle = null;
        }
        return engine;
    };

    // Drawn after a geolocation fix so the user can judge how good it is.
    engine.showAccuracy = function (latlng, radius) {
        if (engine.accuracyCircle) map.removeLayer(engine.accuracyCircle);
        if (!radius) return engine;
        engine.accuracyCircle = L.circle(latlng, {
            radius: radius, weight: 1, opacity: 0.5, fillOpacity: 0.1
        }).addTo(map);
        return engine;
    };

    if (cfg.onMapClick) {
        map.on('click', function (e) { cfg.onMapClick(e.latlng); });
    }

    // --- many points mode (DJMap) ---------------------------------------
    engine.setData = function (payload) {
        return gt_map_render_data(engine, payload || {});
    };

    engine.fitPoints = function () {
        var bounds = [];
        Object.keys(engine.layers).forEach(function (name) {
            var group = engine.layers[name].group;
            if (group.getLayers && group.getLayers().length) {
                bounds.push(group.getBounds());
            }
        });
        if (!bounds.length) return engine;
        var all = bounds[0];
        for (var i = 1; i < bounds.length; i++) all.extend(bounds[i]);
        if (all.isValid()) {
            engine._moveProgrammatically(function () {
                map.fitBounds(all, {padding: [24, 24]});
            });
        }
        return engine;
    };

    engine.destroy = function () {
        if (engine._moveTimer) clearTimeout(engine._moveTimer);
        map.off();
        map.remove();
        if (id) delete _gt_maps[id];
    };

    if (id) _gt_maps[id] = engine;
    return engine;
}

// --- dashboard payload rendering ----------------------------------------

// Coloured or icon-bearing points become an L.divIcon so any colour the API
// sends works without shipping a PNG per colour. font-awesome is already
// bundled, so icon names need no new vendor.
function gt_map_marker_icon(point, layer) {
    var color = point.color || layer.color;
    var icon = point.icon || layer.icon;
    if (!color && !icon) return null;

    // Built as DOM, not as an HTML string: `color` and `icon` come straight
    // from the API payload, and concatenating them into markup made them an
    // injection sink. Leaflet 1.x accepts an Element for `html` (see
    // DivIcon.createIcon), so nothing has to be escaped -- `style.background`
    // goes through the CSSOM, which drops anything that is not a valid colour,
    // and className cannot carry markup.
    var pin = document.createElement('span');
    pin.className = 'gt-map-pin';
    pin.style.background = color || '#3388ff';
    if (icon) {
        var i = document.createElement('i');
        i.className = icon;
        pin.appendChild(i);
    }
    return L.divIcon({
        className: 'gt-map-divicon',
        html: pin,
        iconSize: [24, 24],
        iconAnchor: [12, 24],
        popupAnchor: [0, -24]
    });
}

function gt_map_build_marker(point, layer) {
    var icon = gt_map_marker_icon(point, layer);
    var marker = L.marker([point.lat, point.lng], icon ? {icon: icon} : {});
    if (point.title) marker.bindTooltip(String(point.title));
    // popup is HTML by design: the API owns it and it is rendered server side.
    if (point.popup) marker.bindPopup(point.popup);
    if (point.url) {
        marker.on('click', function () { window.location.href = point.url; });
    }
    return marker;
}

function gt_map_layer_group(useCluster) {
    if (useCluster && typeof L.markerClusterGroup === 'function') {
        return L.markerClusterGroup();
    }
    if (useCluster) {
        console.warn('djgentelella maps: clustering was requested but ' +
                     'Leaflet.markercluster is missing -- falling back to a ' +
                     'plain layer group. Set use_maps in DEFAULT_JS_IMPORTS.');
    }
    return L.layerGroup();
}

function gt_map_render_data(engine, payload) {
    var map = engine.map;

    // Drop whatever a previous fetch put on the map.
    Object.keys(engine.layers).forEach(function (name) {
        map.removeLayer(engine.layers[name].group);
    });
    engine.layers = {};
    if (engine.heatLayer) {
        map.removeLayer(engine.heatLayer);
        engine.heatLayer = null;
    }
    if (engine.control) {
        map.removeControl(engine.control);
        engine.control = null;
    }

    // Single layer shorthand: a payload may just carry "points".
    var layers = payload.layers || [];
    if (!layers.length && payload.points) {
        layers = [{name: '', points: payload.points}];
    }

    var defaultCluster = payload.cluster === true;
    var overlays = {};
    var weighted = [];

    layers.forEach(function (layer, index) {
        var useCluster = layer.cluster === undefined ? defaultCluster : layer.cluster;
        var group = gt_map_layer_group(useCluster);
        (layer.points || []).forEach(function (point) {
            if (!isFinite(point.lat) || !isFinite(point.lng)) return;
            group.addLayer(gt_map_build_marker(point, layer));
            weighted.push([point.lat, point.lng, point.weight || 1]);
        });
        var name = layer.name || ('layer-' + index);
        engine.layers[name] = {group: group, config: layer};
        if (layer.visible !== false) group.addTo(map);
        if (layer.name) overlays[layer.name] = group;
    });

    var heat = payload.heatmap;
    if (heat) {
        if (typeof L.heatLayer === 'function') {
            var heatPoints = heat.points && heat.points.length ? heat.points : weighted;
            engine.heatLayer = L.heatLayer(heatPoints, {
                radius: heat.radius || 25,
                blur: heat.blur || 15,
                max: heat.max || 1.0
            });
            if (heat.visible !== false) engine.heatLayer.addTo(map);
            overlays[heat.name || 'Heatmap'] = engine.heatLayer;
        } else {
            console.warn('djgentelella maps: a heatmap was requested but ' +
                         'Leaflet.heat is missing -- skipping it. Set ' +
                         'use_maps in DEFAULT_JS_IMPORTS.');
        }
    }

    // The heatmap sits in the same control as the marker layers, because to a
    // user they are the same kind of thing: a switchable overlay.
    if (Object.keys(overlays).length > 1) {
        engine.control = L.control.layers(null, overlays).addTo(map);
    }

    var center = payload.center && gt_parse_latlng(payload.center.join(','));
    if (center) {
        engine._moveProgrammatically(function () {
            map.setView([center.lat, center.lng], payload.zoom || engine.options.zoom);
        });
    } else if (payload.fit_bounds !== false) {
        engine.fitPoints();
    }
    return engine;
}
