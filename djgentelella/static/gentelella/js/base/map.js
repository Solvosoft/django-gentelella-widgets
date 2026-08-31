// DJMap dashboard widget: a map whose points come from an API, the sibling of
// $.fn.gentelella_chart. Every data-* other than the reserved ones is resolved
// through gt_resolve_value and sent as a query parameter, so filters written
// for the chart widget behave identically here.
$.fn.gentelella_map = function () {
    var reservedAttrs = ['url', 'widget', 'refetchOnMove', 'height', 'zoom',
                         'center', 'minZoom', 'maxZoom', 'tileUrl',
                         'tileAttribution', 'geocoderUrl', 'mapInstance'];

    var collectParams = function ($element) {
        var params = {};
        $.each($element.data(), function (key, value) {
            if (reservedAttrs.indexOf(key) !== -1) return;
            // Only primitives. jQuery's .data() store is shared with whatever
            // else the page put there -- notably our own mapInstance -- and
            // $.param() walks nested objects and *calls* any function it finds
            // while serialising, which detaches Leaflet's methods from their
            // objects and throws deep inside the ajax call.
            var resolved = gt_resolve_value(value);
            var type = typeof resolved;
            if (type === 'string' || type === 'number' || type === 'boolean') {
                params[key] = resolved;
            }
        });
        return params;
    };

    $.each($(this), function (i, e) {
        var $element = $(e);
        var url = $element.data('url');
        var container = $element.find('.gt-map')[0];
        if (!container) return;
        // createGTMap keys its registry by element id, which is what makes a
        // re-render replace the old map instead of stacking a new one on a
        // container Leaflet already claimed.
        if (!container.id) {
            container.id = 'gt_map_' + i + '_' + (url || '').replace(/\W+/g, '_');
        }

        var engine = createGTMap(container, gt_map_config_from_data($element));
        if (!engine) return;

        var load = function (extra) {
            var params = $.extend(collectParams($element), extra || {});
            $.ajax({
                url: url,
                type: 'GET',
                dataType: 'json',
                data: params,
                success: function (result) {
                    engine.setData(result);
                },
                error: function (xhr, resp, text) {
                    // The map just stays blank, so the console is the only
                    // place this ever surfaces -- make it an error, not a log.
                    console.error('Error loading map:', url, text);
                }
            });
        };

        // Re-fetching as the map moves is opt-in: with fit_bounds on, the
        // initial fit itself fires moveend, so an always-on handler would loop
        // fetch -> fit -> moveend -> fetch. _programmaticMove guards the fits
        // the engine performs itself.
        if ($element.data('refetch-on-move') === true ||
            $element.data('refetch-on-move') === 'true') {
            engine.map.on('moveend', function () {
                if (engine._programmaticMove) return;
                if (engine._moveTimer) clearTimeout(engine._moveTimer);
                engine._moveTimer = setTimeout(function () {
                    var b = engine.map.getBounds();
                    load({
                        bbox: [b.getSouth(), b.getWest(),
                               b.getNorth(), b.getEast()].join(','),
                        zoom: engine.map.getZoom()
                    });
                }, 500);
            });
        }

        engine.reload = function (extra) { load(extra); return engine; };
        // Mirrors chartInstance; the selenium tests assert on it.
        $element.data('mapInstance', engine);
        load();
    });
};

// Re-fetch a dashboard map, for wiring a filter form in one line:
//   $('#filters').on('change', function(){ refreshGentelellaMap('#places'); });
//
// Assigned to window explicitly: createbasejs wraps every jquery_plugins file
// in a single (function($){...})(jQuery), so a plain declaration here would
// stay trapped inside that closure and page code could not call it.
window.refreshGentelellaMap = function (selector, extra) {
    $(selector).each(function (i, e) {
        var engine = $(e).data('mapInstance');
        if (engine) engine.reload(extra);
    });
};
