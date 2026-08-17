// MapPointInput consumer: a text input holding "lat,lng" kept in sync with a
// Leaflet marker. Built on createGTMap (maplib.js), the way voicedictation.js
// is built on createProgressiveVoiceEngine.

// Widgets by input id. Same reason as _voice_dictation_engines: a re-render
// (api_list.js, a reopened modal, a cloned formset row) reinitialises the same
// id on a brand new node, and the previous Leaflet map has to be torn down or
// it throws "Map container is already initialized" and leaks.
var _gt_map_point_widgets = {};

function getMapPointWidget(element) {
    var id = element.id;
    var previous = _gt_map_point_widgets[id];
    if (previous) {
        previous.destroy();
        delete _gt_map_point_widgets[id];
    }

    var input = $(element);
    var container = document.getElementById(id + '_map');
    if (!container) return null;

    var cfg = gt_map_config_from_data(input);
    // A disabled/readonly input still gets a pannable map, but nothing may
    // change its value.
    var readonly = element.readOnly || element.disabled;
    cfg.readonly = readonly;

    var statusEl = $('#' + id + '_status');
    var searchEl = $('#' + id + '_search');
    var resultsEl = $('#' + id + '_results');
    var locateBtn = $('#' + id + '_locate');
    var clearBtn = $('#' + id + '_clear');

    var typingTimer = null;
    var searchTimer = null;
    var basedTimer = null;
    var searchAbort = null;
    var basedAbort = null;

    function status(message, invalid) {
        statusEl.text(message || '');
        input.toggleClass('is-invalid', !!invalid);
    }

    // input first: that is what validations and autosave listen to for a
    // programmatic change; change keeps the conventional behaviour. Leaving
    // this out is what makes django-location-field break Parsley.
    function notify() {
        element.dispatchEvent(new Event('input', {bubbles: true}));
        element.dispatchEvent(new Event('change', {bubbles: true}));
    }

    function writeValue(latlng) {
        element.value = gt_format_latlng(latlng.lat, latlng.lng, cfg.precision);
        status('');
        notify();
    }

    function onPicked(latlng) {
        if (readonly) return;
        engine.setPoint(latlng, false);
        writeValue(latlng);
    }

    cfg.onMapClick = onPicked;
    cfg.onMarkerDrag = function (latlng) {
        if (readonly) return;
        writeValue(latlng);
    };

    var engine = createGTMap(container, cfg);
    if (!engine) return null;

    // Initial value: place the marker, or say why it was ignored. A malformed
    // stored value must not silently drop a pin somewhere plausible.
    var initial = gt_parse_latlng(element.value);
    if (initial) {
        engine.setPoint(initial, false);
        engine.map.setView([initial.lat, initial.lng], cfg.zoom);
    } else if (element.value && element.value.trim()) {
        status(gettext('Not a valid "latitude,longitude" value'), true);
    }

    if (readonly && engine.marker) {
        engine.marker.dragging.disable();
    }

    // --- typing in the input --------------------------------------------
    // addEventListener, not jQuery's .on(): jQuery runs the handlers of an
    // event in registration order and stops the whole dispatch when one of
    // them throws. bootstrap-maxlength binds 'input' on any field carrying a
    // maxlength attribute (which a max_length model field produces) and throws
    // from it when the field was never focused. Keeping the map in sync with
    // the value must not depend on an unrelated plugin behaving.
    function onInput() {
        if (typingTimer) clearTimeout(typingTimer);
        typingTimer = setTimeout(function () {
            var value = element.value.trim();
            if (!value) {
                engine.clear();
                status('');
                return;
            }
            var point = gt_parse_latlng(value);
            if (point) {
                engine.setPoint(point);
                status('');
            } else {
                status(gettext('Not a valid "latitude,longitude" value'), true);
            }
        }, 300);
    }
    element.addEventListener('input', onInput);

    // --- clear ------------------------------------------------------------
    clearBtn.on('click.gtmap', function () {
        if (readonly) return;
        element.value = '';
        engine.clear();
        status('');
        notify();
    });

    // --- use my location --------------------------------------------------
    // Browsers only answer getCurrentPosition in a secure context (https or
    // localhost) and fail with a permission error otherwise, so the button is
    // removed rather than left to look broken.
    if (!window.isSecureContext || !navigator.geolocation || readonly) {
        locateBtn.remove();
    } else {
        locateBtn.on('click.gtmap', function () {
            status(gettext('Locating...'));
            navigator.geolocation.getCurrentPosition(function (position) {
                var latlng = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude
                };
                engine.setPoint(latlng);
                engine.showAccuracy(latlng, position.coords.accuracy);
                writeValue(latlng);
            }, function (error) {
                status(gettext('Could not get your location') + ': ' + error.message,
                       true);
            }, {enableHighAccuracy: true, timeout: 10000});
        });
    }

    // --- address search ---------------------------------------------------
    function renderResults(results) {
        resultsEl.empty();
        if (!results.length) {
            resultsEl.addClass('d-none');
            return;
        }
        results.forEach(function (result) {
            $('<li class="list-group-item"></li>')
                .text(result.label)
                .on('click', function () {
                    engine.setPoint(result, false);
                    writeValue(result);
                    engine.map.setView([result.lat, result.lng], cfg.zoom);
                    resultsEl.addClass('d-none');
                    searchEl.val('');
                })
                .appendTo(resultsEl);
        });
        resultsEl.removeClass('d-none');
    }

    if (searchEl.length && !readonly) {
        searchEl.on('input.gtmap', function () {
            if (searchTimer) clearTimeout(searchTimer);
            if (searchAbort) searchAbort.abort();
            var query = searchEl.val().trim();
            if (query.length < 3) {
                resultsEl.addClass('d-none');
                return;
            }
            searchTimer = setTimeout(function () {
                searchAbort = new AbortController();
                gt_map_geocode(query, {
                    geocoderUrl: cfg.geocoderUrl,
                    signal: searchAbort.signal
                }).then(renderResults).catch(function (error) {
                    if (error.name === 'AbortError') return;
                    status(gettext('Address search failed'), true);
                });
            }, 400);
        });
    }

    // --- based fields -----------------------------------------------------
    // Geocode from other fields (country, city...). Selectors go through
    // gt_resolve_value, so the same syntax the chart filters use works here.
    var basedBound = [];
    var basedFields = input.data('based-fields') || [];
    if (typeof basedFields === 'string') {
        // A malformed data-based-fields must cost the geocoding, not the whole
        // widget: without this the throw aborts the rest of the wiring and the
        // user gets an input with no map at all.
        try {
            basedFields = JSON.parse(basedFields);
        } catch (error) {
            console.error('map point: invalid data-based-fields', basedFields,
                          error);
            basedFields = [];
        }
    }
    var basedOverwrite = input.data('based-overwrite') === 'true' ||
                         input.data('based-overwrite') === true;

    if (basedFields.length && !readonly) {
        // Resolve inside the surrounding form first so a formset row picks up
        // its own fields; base/formset.js already rewrites __prefix__ and
        // re-runs gt_find_initialize on the clone, so no prefix arithmetic is
        // needed here.
        var scope = input.closest('form, .dynamic-form, tr');

        function basedValues() {
            return basedFields.map(function (selector) {
                if (typeof selector === 'string' &&
                    (selector.startsWith('#') || selector.startsWith('.'))) {
                    var local = scope.find(selector).first();
                    if (local.length) return local.val() || local.text();
                }
                return gt_resolve_value(selector);
            }).filter(function (value) { return value; });
        }

        function onBasedChange() {
            // Never stomp a point the user already placed -- the worst habit of
            // the library this was modelled on.
            if (!basedOverwrite && element.value.trim()) return;
            if (basedTimer) clearTimeout(basedTimer);
            if (basedAbort) basedAbort.abort();
            var address = basedValues().join(', ');
            if (!address) return;
            basedTimer = setTimeout(function () {
                basedAbort = new AbortController();
                gt_map_geocode(address, {
                    geocoderUrl: cfg.geocoderUrl,
                    limit: 1,
                    signal: basedAbort.signal
                }).then(function (results) {
                    if (!results.length) return;
                    if (!basedOverwrite && element.value.trim()) return;
                    engine.setPoint(results[0]);
                    writeValue(results[0]);
                }).catch(function (error) {
                    if (error.name !== 'AbortError') console.warn(error);
                });
            }, 400);
        }

        basedFields.forEach(function (selector) {
            if (typeof selector !== 'string') return;
            if (!selector.startsWith('#') && !selector.startsWith('.')) return;
            var field = scope.find(selector).first();
            if (!field.length) field = $(selector).first();
            field.on('change.gtmap keyup.gtmap', onBasedChange);
            // Remembered because these handlers sit on *other* elements: the
            // `input.off('.gtmap')` in destroy() only reaches this widget's own
            // input, so without this list a re-rendered widget (a formset row,
            // a reopened modal) leaves a live handler on a sibling field
            // closing over an engine that no longer has a map. The handler is
            // named on the way out too, since two widgets can watch the same
            // field and a bare .off('.gtmap') would unbind the other one.
            basedBound.push(function () {
                field.off('change.gtmap keyup.gtmap', onBasedChange);
            });
        });
    }

    var widget = {
        engine: engine,
        destroy: function () {
            if (typingTimer) clearTimeout(typingTimer);
            if (searchTimer) clearTimeout(searchTimer);
            if (basedTimer) clearTimeout(basedTimer);
            if (searchAbort) searchAbort.abort();
            if (basedAbort) basedAbort.abort();
            element.removeEventListener('input', onInput);
            input.off('.gtmap');
            searchEl.off('.gtmap');
            locateBtn.off('.gtmap');
            clearBtn.off('.gtmap');
            basedBound.forEach(function (unbind) { unbind(); });
            engine.destroy();
        }
    };
    _gt_map_point_widgets[id] = widget;
    return widget;
}

function build_map_point(instances) {
    instances.each(function (index, element) {
        getMapPointWidget(element);
    });
}
