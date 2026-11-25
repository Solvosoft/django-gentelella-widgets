/**
  The form widgets of djgentelella.widgets.extras and widgets.geocoding:
  StarRatingInput, RangeInput, ComboboxInput, QRCodeInput (+ QRCodeView) and
  GeocodedAddressInput. Registered in document.gtwidgets (widgets.js).

  Libraries a widget needs only sometimes (qrcode-generator, jsQR,
  Cropper.js) are not in the vendors bundle: the widget passes their static
  url in a data attribute and gt_load_script() loads each one once, the first
  time a widget asks for it.
**/
document.gt_lazy_assets = document.gt_lazy_assets || {};

function gt_load_script(url) {
    if (!url) return Promise.reject(new Error('gt_load_script: no url'));
    if (!document.gt_lazy_assets[url]) {
        document.gt_lazy_assets[url] = new Promise(function (resolve, reject) {
            var script = document.createElement('script');
            script.src = url;
            script.async = true;
            script.onload = function () { resolve(); };
            script.onerror = function () {
                // Forget it, so a later widget can try again.
                delete document.gt_lazy_assets[url];
                reject(new Error('could not load ' + url));
            };
            document.head.appendChild(script);
        });
    }
    return document.gt_lazy_assets[url];
}

function gt_load_style(url) {
    if (!url) return Promise.resolve();
    if (!document.gt_lazy_assets[url]) {
        document.gt_lazy_assets[url] = new Promise(function (resolve) {
            var link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = url;
            // A missing stylesheet degrades the look, not the widget.
            link.onload = link.onerror = function () { resolve(); };
            document.head.appendChild(link);
        });
    }
    return document.gt_lazy_assets[url];
}

/* Once per element: a re-initialisation (api_list.js, a reopened modal)
   must not bind the handlers twice. */
function gt_widget_once(element, key) {
    var flag = 'gtReady' + key;
    if (element.dataset[flag]) return false;
    element.dataset[flag] = '1';
    return true;
}

/* The input of the field `name` in the same form (and prefix) as `element`. */
function gt_sibling_field(element, name) {
    var cut = element.name.lastIndexOf('-');
    var full = cut === -1 ? name : element.name.substring(0, cut) + '-' + name;
    var scope = element.form || document;
    var found = null;
    scope.querySelectorAll('input, select, textarea').forEach(function (field) {
        if (!found && field.name === full) found = field;
    });
    return found;
}

function gt_fire(element) {
    element.dispatchEvent(new Event('input', {bubbles: true}));
    element.dispatchEvent(new Event('change', {bubbles: true}));
}

/* ---- StarRatingInput ---------------------------------------------------- */
function gt_star_rating(instance) {
    instance.each(function (i, input) {
        if (!gt_widget_once(input, 'Rating')) return;
        var wrapper = input.closest('.gt-rating');
        var stars = wrapper.querySelector('.gt-rating-stars');
        var buttons = Array.prototype.slice.call(
            wrapper.querySelectorAll('.gt-rating-star'));
        var readonly = input.getAttribute('data-readonly') === 'true';
        input.classList.add('visually-hidden');
        input.setAttribute('tabindex', '-1');
        stars.classList.remove('d-none');

        var current = function () {
            var value = parseInt(input.value, 10);
            return isNaN(value) ? 0 : value;
        };
        var paint = function (value) {
            buttons.forEach(function (button) {
                var on = parseInt(button.getAttribute('data-value'), 10) <= value;
                button.classList.toggle('gt-rating-on', on);
                button.setAttribute('aria-pressed', on ? 'true' : 'false');
                button.querySelector('i').className = 'fa ' + (on ? 'fa-star' : 'fa-star-o');
            });
        };
        paint(current());
        input.addEventListener('change', function () { paint(current()); });
        if (readonly || input.disabled) return;

        var set = function (value) {
            input.value = String(value);
            paint(value);
            gt_fire(input);
        };
        buttons.forEach(function (button) {
            var value = parseInt(button.getAttribute('data-value'), 10);
            button.addEventListener('click', function () {
                // A second click on the only lit star clears it.
                set(current() === value && value === 1 ? 0 : value);
            });
            button.addEventListener('mouseenter', function () { paint(value); });
            button.addEventListener('focus', function () { paint(value); });
            button.addEventListener('keydown', function (event) {
                var next = null;
                if (event.key === 'ArrowRight' || event.key === 'ArrowUp') {
                    next = Math.min(current() + 1, buttons.length);
                } else if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') {
                    next = Math.max(current() - 1, 0);
                }
                if (next === null) return;
                event.preventDefault();
                set(next);
                if (next > 0) buttons[next - 1].focus();
            });
        });
        stars.addEventListener('mouseleave', function () { paint(current()); });
        stars.addEventListener('focusout', function () { paint(current()); });
        var clear = wrapper.querySelector('.gt-rating-clear');
        if (clear) clear.addEventListener('click', function () { set(0); });
    });
}

/* ---- RangeInput --------------------------------------------------------- */
function gt_range_input(instance) {
    instance.each(function (i, input) {
        if (!gt_widget_once(input, 'Range')) return;
        var output = input.id ? document.getElementById(input.id + '_value') : null;
        if (!output) return;
        var suffix = input.getAttribute('data-suffix') || '';
        var show = function () { output.textContent = input.value + suffix; };
        input.addEventListener('input', show);
        input.addEventListener('change', show);
        show();
    });
}

/* ---- ComboboxInput ------------------------------------------------------ */
function gt_combobox(instance) {
    instance.each(function (i, element) {
        var $element = $(element);
        var context = {
            tags: true,
            placeholder: gettext('Select or write a value'),
            allowClear: !element.required,
            width: '100%'
        };
        extract_select2_context(context, $element);
        if ($element.hasClass('select2-hidden-accessible')) $element.select2('destroy');
        $element.select2(context);
    });
}

/* ---- QRCodeInput / QRCodeView ------------------------------------------- */
function gt_qr_draw(canvas, text, size, status) {
    var context = canvas.getContext('2d');
    if (!text) {
        canvas.width = canvas.height = 0;
        if (status) status.textContent = '';
        return;
    }
    var code;
    try {
        code = qrcode(0, 'M');
        code.addData(unescape(encodeURIComponent(text)));
        code.make();
    } catch (error) {
        canvas.width = canvas.height = 0;
        if (status) status.textContent = gettext('The text is too long for a QR code.');
        return;
    }
    if (status) status.textContent = '';
    var count = code.getModuleCount();
    var margin = 4;
    var cell = Math.max(1, Math.floor(size / (count + margin * 2)));
    var side = cell * (count + margin * 2);
    canvas.width = canvas.height = side;
    context.fillStyle = '#ffffff';
    context.fillRect(0, 0, side, side);
    context.fillStyle = '#000000';
    for (var row = 0; row < count; row++) {
        for (var col = 0; col < count; col++) {
            if (code.isDark(row, col)) {
                context.fillRect((col + margin) * cell, (row + margin) * cell, cell, cell);
            }
        }
    }
    canvas.setAttribute('data-qr-text', text);
}

function gt_qrcode_view(instance) {
    instance.each(function (i, canvas) {
        gt_load_script(canvas.getAttribute('data-qr-lib')).then(function () {
            gt_qr_draw(canvas, canvas.getAttribute('data-value') || '',
                       parseInt(canvas.getAttribute('data-size'), 10) || 120, null);
        }).catch(function (error) { console.error('QRCodeView', error); });
    });
}

function gt_qrcode_scan(input, button) {
    var video = document.getElementById(input.id + '_video');
    var status = document.getElementById(input.id + '_qrstatus');
    var stream = null;
    var detector = null;
    var frame = document.createElement('canvas');
    var stop = function () {
        if (stream) stream.getTracks().forEach(function (track) { track.stop(); });
        stream = null;
        video.classList.add('d-none');
        button.classList.remove('active');
    };
    var found = function (text) {
        stop();
        input.value = text;
        gt_fire(input);
    };
    var tick = function () {
        if (!stream) return;
        if (video.readyState < 2) { requestAnimationFrame(tick); return; }
        if (detector) {
            detector.detect(video).then(function (codes) {
                if (codes.length) found(codes[0].rawValue);
                else requestAnimationFrame(tick);
            }).catch(function () { requestAnimationFrame(tick); });
            return;
        }
        frame.width = video.videoWidth;
        frame.height = video.videoHeight;
        var context = frame.getContext('2d');
        context.drawImage(video, 0, 0, frame.width, frame.height);
        var image = context.getImageData(0, 0, frame.width, frame.height);
        var code = jsQR(image.data, image.width, image.height);
        if (code && code.data) found(code.data);
        else requestAnimationFrame(tick);
    };
    button.addEventListener('click', function () {
        if (stream) { stop(); return; }
        var ready = ('BarcodeDetector' in window)
            ? Promise.resolve().then(function () {
                detector = new BarcodeDetector({formats: ['qr_code']});
            })
            : gt_load_script(input.getAttribute('data-jsqr-lib'));
        ready.then(function () {
            return navigator.mediaDevices.getUserMedia(
                {video: {facingMode: 'environment'}, audio: false});
        }).then(function (media) {
            stream = media;
            video.srcObject = media;
            video.classList.remove('d-none');
            button.classList.add('active');
            return video.play();
        }).then(function () {
            requestAnimationFrame(tick);
        }).catch(function (error) {
            stop();
            status.textContent = gettext('The camera could not be opened.');
            console.error('QRCodeInput', error);
        });
    });
}

function gt_qrcode_input(instance) {
    instance.each(function (i, input) {
        if (!gt_widget_once(input, 'QR')) return;
        var canvas = document.getElementById(input.id + '_qr');
        var status = document.getElementById(input.id + '_qrstatus');
        var size = parseInt(input.getAttribute('data-size'), 10) || 160;
        gt_load_script(input.getAttribute('data-qr-lib')).then(function () {
            var draw = function () { gt_qr_draw(canvas, input.value, size, status); };
            input.addEventListener('input', draw);
            input.addEventListener('change', draw);
            draw();
        }).catch(function (error) { console.error('QRCodeInput', error); });
        var button = document.getElementById(input.id + '_scan');
        // The camera exists only in a secure context (https or localhost).
        if (button && window.isSecureContext && navigator.mediaDevices
                && navigator.mediaDevices.getUserMedia) {
            button.classList.remove('d-none');
            gt_qrcode_scan(input, button);
        }
    });
}

/* ---- GeocodedAddressInput ----------------------------------------------- */
function gt_geocoded_address(instance) {
    instance.each(function (i, input) {
        if (!gt_widget_once(input, 'Geocode')) return;
        var url = input.getAttribute('data-geocode-url');
        if (!url) return;  // no geocoder configured: a plain text input
        var button = document.getElementById(input.id + '_geocode');
        var list = document.getElementById(input.id + '_places');
        var pointName = input.getAttribute('data-point-field');
        var replace = input.getAttribute('data-replace-text') === 'true';

        var choose = function (place) {
            if (replace) input.value = place.label;
            if (pointName) {
                var point = gt_sibling_field(input, pointName);
                if (point) {
                    point.value = place.point;
                    gt_fire(point);
                }
            }
            list.classList.add('d-none');
            list.textContent = '';
            gt_fire(input);
        };
        var show = function (places) {
            list.textContent = '';
            if (!places.length) {
                var empty = document.createElement('div');
                empty.className = 'list-group-item text-muted';
                empty.textContent = list.getAttribute('data-empty');
                list.appendChild(empty);
            }
            places.forEach(function (place) {
                var item = document.createElement('button');
                item.type = 'button';
                item.className = 'list-group-item list-group-item-action gt-geocode-place';
                item.textContent = place.label;
                item.setAttribute('data-point', place.point);
                item.addEventListener('click', function () { choose(place); });
                list.appendChild(item);
            });
            list.classList.remove('d-none');
        };
        var search = function () {
            var query = input.value.trim();
            if (!query) return;
            button.disabled = true;
            fetch(url + '?' + new URLSearchParams({q: query}), {
                credentials: 'same-origin', headers: {'Accept': 'application/json'}
            }).then(function (response) {
                return response.json().then(function (body) {
                    if (!response.ok) throw new Error(body.error || response.status);
                    return body;
                });
            }).then(function (body) {
                show(body.results || []);
            }).catch(function (error) {
                list.textContent = '';
                var item = document.createElement('div');
                item.className = 'list-group-item text-danger';
                item.textContent = error.message;
                list.appendChild(item);
                list.classList.remove('d-none');
            }).finally(function () { button.disabled = false; });
        };
        button.addEventListener('click', search);
        // Enter searches instead of submitting the form.
        input.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                search();
            }
        });
    });
}
