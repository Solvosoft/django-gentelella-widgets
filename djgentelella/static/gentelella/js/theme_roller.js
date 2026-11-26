/* The theme roller page (djgentelella.theme): a colour picker next to each
 * colour field, and the preview stylesheet reloaded as the values change. The
 * CSS comes from the server (the same writer as the saved theme), so only
 * valid values are ever applied. */
(function () {
    'use strict';
    var form = document.getElementById('gt-theme-form');
    var link = document.getElementById('gt-theme-preview-css');
    if (!form || !link) {
        return;
    }
    var HEX = /^#[0-9a-fA-F]{6}$/;
    var SHORT = /^#([0-9a-fA-F])([0-9a-fA-F])([0-9a-fA-F])$/;

    // #rgb is accepted too (the server stores it as #rrggbb).
    function longHex(value) {
        var short = SHORT.exec(value);
        if (short) {
            return ('#' + short[1] + short[1] + short[2] + short[2] + short[3] + short[3]).toLowerCase();
        }
        return HEX.test(value) ? value.toLowerCase() : null;
    }
    var timer = null;

    function query() {
        var params = new URLSearchParams();
        form.querySelectorAll('input.gt-theme-color, select[name=font], input[name=border_radius]')
            .forEach(function (field) { params.set(field.name, field.value.trim()); });
        return params.toString();
    }

    function refresh() {
        window.clearTimeout(timer);
        timer = window.setTimeout(function () {
            link.href = form.dataset.preview + '?' + query();
        }, 150);
    }

    form.querySelectorAll('input.gt-theme-color').forEach(function (field) {
        var picker = document.createElement('input');
        picker.type = 'color';
        picker.className = 'form-control form-control-color gt-theme-picker';
        picker.title = field.placeholder;
        picker.setAttribute('aria-label', (field.labels && field.labels[0]
            ? field.labels[0].textContent : field.name) + ' (picker)');
        picker.value = longHex(field.value.trim()) || '#ffffff';
        var group = document.createElement('div');
        group.className = 'input-group';
        field.parentNode.insertBefore(group, field);
        group.appendChild(field);
        group.appendChild(picker);
        picker.addEventListener('input', function () {
            field.value = picker.value;
            refresh();
        });
        field.addEventListener('input', function () {
            var color = longHex(field.value.trim());
            if (color) {
                picker.value = color;
            }
            refresh();
        });
    });
    form.querySelectorAll('select[name=font], input[name=border_radius]').forEach(function (field) {
        field.addEventListener('input', refresh);
        field.addEventListener('change', refresh);
        if (window.jQuery) {  // select2 announces its change through jQuery
            window.jQuery(field).on('change', refresh);
        }
    });
}());
