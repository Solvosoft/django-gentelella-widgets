/* The circular dial behind NumberKnobInput.
 *
 * Replaces jQuery-Knob (2015, unmaintained), which drew into a <canvas> --
 * blurry on any screen past 1x -- and rebuilt its own keyboard handling.
 *
 * The design here is deliberately smaller than that: the <input type="number">
 * the widget renders stays in the DOM as the value, the visible readout and
 * the focusable control, so arrow keys, typing, min/max/step validation and
 * what a screen reader announces are all the browser's own. The svg is
 * decorative -- aria-hidden, never a tab stop -- and only adds what an input
 * cannot do: dragging round the dial and the wheel.
 *
 * Options come off the same data-* attributes jQuery-Knob read, so nothing in
 * python changed: data-min, data-max, data-step, data-width, data-fgcolor,
 * data-bgcolor, data-thickness.
 */
$.fn.gt_knob = function () {
    var TAU = Math.PI * 2;
    // r=42 in a 100x100 viewBox leaves room for the thickest stroke we allow.
    var RADIUS = 42;
    var CIRCUMFERENCE = TAU * RADIUS;

    function number(value, fallback) {
        var parsed = parseFloat(value);
        return isNaN(parsed) ? fallback : parsed;
    }

    /* How many decimals the step implies, so 0.1 does not produce 33.900000004. */
    function decimals(step) {
        var text = String(step);
        var dot = text.indexOf('.');
        return dot === -1 ? 0 : text.length - dot - 1;
    }

    function svg(name, attrs) {
        var node = document.createElementNS('http://www.w3.org/2000/svg', name);
        for (var key in attrs) {
            node.setAttribute(key, attrs[key]);
        }
        return node;
    }

    $.each($(this), function (index, input) {
        // A formset clones its template and re-runs the initialisers over the
        // whole subtree, so the same input can arrive here twice.
        if (input.gt_knob) {
            return;
        }

        var data = input.dataset;
        var min = number(data.min, number(input.min, 0));
        var max = number(data.max, number(input.max, 100));
        var step = number(data.step, number(input.step, 1));
        if (max <= min) {
            max = min + 1;
        }
        if (step <= 0) {
            step = 1;
        }
        var places = decimals(step);

        var wrapper = document.createElement('div');
        wrapper.className = 'gt-knob';
        if (data.width) {
            wrapper.style.setProperty('--gt-knob-size', parseFloat(data.width) + 'px');
        }
        if (data.fgcolor) {
            wrapper.style.setProperty('--gt-knob-color', data.fgcolor);
        }
        if (data.bgcolor) {
            wrapper.style.setProperty('--gt-knob-track', data.bgcolor);
        }
        if (data.thickness) {
            // jQuery-Knob took a fraction of the radius; keep that meaning.
            wrapper.style.setProperty(
                '--gt-knob-thickness', (parseFloat(data.thickness) * RADIUS) + '');
        }

        var dial = svg('svg', {
            viewBox: '0 0 100 100', class: 'gt-knob-dial', 'aria-hidden': 'true',
            focusable: 'false'
        });
        var track = svg('circle', {
            class: 'gt-knob-track', cx: 50, cy: 50, r: RADIUS
        });
        var value_arc = svg('circle', {
            class: 'gt-knob-value', cx: 50, cy: 50, r: RADIUS,
            // Drawn from the top, clockwise, instead of from three o'clock.
            transform: 'rotate(-90 50 50)',
            'stroke-dasharray': CIRCUMFERENCE
        });
        dial.appendChild(track);
        dial.appendChild(value_arc);

        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(dial);
        wrapper.appendChild(input);
        input.classList.add('gt-knob-input');

        function current() {
            var value = number(input.value, min);
            return Math.min(max, Math.max(min, value));
        }

        function paint() {
            var fraction = (current() - min) / (max - min);
            value_arc.setAttribute(
                'stroke-dashoffset', CIRCUMFERENCE * (1 - fraction));
        }

        function write(value) {
            value = Math.round((value - min) / step) * step + min;
            value = Math.min(max, Math.max(min, value));
            var text = value.toFixed(places);
            if (text === input.value) {
                return;
            }
            input.value = text;
            paint();
            $(input).trigger('change');
        }

        function editable() {
            return !(input.disabled || input.readOnly);
        }

        /* Where the pointer is, as a fraction of the way round from the top. */
        function fraction_at(event) {
            var box = dial.getBoundingClientRect();
            var angle = Math.atan2(
                event.clientY - (box.top + box.height / 2),
                event.clientX - (box.left + box.width / 2)) + Math.PI / 2;
            if (angle < 0) {
                angle += TAU;
            }
            return angle / TAU;
        }

        var dragging = false;
        var last_fraction = null;

        function drag_to(event) {
            var fraction = fraction_at(event);
            // Crossing twelve o'clock flips the angle between ~0 and ~1. A
            // real drag never covers half the dial between two pointer events,
            // so a jump that big is the seam, not the user.
            if (last_fraction !== null && Math.abs(fraction - last_fraction) > 0.5) {
                fraction = fraction > last_fraction ? 0 : 1;
            }
            last_fraction = fraction;
            write(min + fraction * (max - min));
        }

        dial.addEventListener('pointerdown', function (event) {
            if (!editable()) {
                return;
            }
            dragging = true;
            last_fraction = null;
            // Capture, so the drag survives the pointer leaving the dial --
            // which it does constantly, the control being 42px of circle.
            dial.setPointerCapture(event.pointerId);
            drag_to(event);
            event.preventDefault();
        });

        dial.addEventListener('pointermove', function (event) {
            if (dragging) {
                drag_to(event);
            }
        });

        function stop(event) {
            if (!dragging) {
                return;
            }
            dragging = false;
            last_fraction = null;
            if (dial.hasPointerCapture(event.pointerId)) {
                dial.releasePointerCapture(event.pointerId);
            }
        }
        dial.addEventListener('pointerup', stop);
        dial.addEventListener('pointercancel', stop);

        dial.addEventListener('wheel', function (event) {
            if (!editable()) {
                return;
            }
            event.preventDefault();
            write(current() + (event.deltaY < 0 ? step : -step));
        }, {passive: false});

        // Typing in the input, arrow keys, a form reset, or any code setting
        // the value and firing change: all of them repaint through here.
        $(input).on('input change', paint);

        input.gt_knob = {paint: paint, write: write};
        paint();
    });
    return this;
};
