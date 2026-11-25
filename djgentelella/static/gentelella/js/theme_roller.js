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
        picker.value = HEX.test(field.value) ? field.value : '#ffffff';
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
            if (HEX.test(field.value.trim())) {
                picker.value = field.value.trim();
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
