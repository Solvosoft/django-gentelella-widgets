/**
  LOVPopupSelect (djgentelella.widgets.lov): a LOV searched in a modal, page
  by page, over the same endpoint as LOVSelect (gtapis/lov/<name>/: q, page,
  the parents; answers {results: [{id, text}], pagination: {more}}).

  The value is the only option of a hidden select. Labels come from the
  server and are written with textContent.
**/
function gt_lov_popup(instance) {
    instance.each(function (i, select) {
        if (!gt_widget_once(select, 'LovPopup')) return;
        var wrapper = select.closest('.gt-lov-popup');
        var label = wrapper.querySelector('.gt-lov-popup-label');
        var modalEl = wrapper.querySelector('.gt-lov-popup-modal');
        var search = modalEl.querySelector('.gt-lov-popup-search');
        var results = modalEl.querySelector('.gt-lov-popup-results');
        var empty = modalEl.querySelector('.gt-lov-popup-empty');
        var prev = modalEl.querySelector('.gt-lov-popup-prev');
        var next = modalEl.querySelector('.gt-lov-popup-next');
        var pageLabel = modalEl.querySelector('.gt-lov-popup-page');
        var depends = {};
        try {
            depends = JSON.parse(select.getAttribute('data-lov-depends') || '{}');
        } catch (e) {
            console.error('LOVPopupSelect: invalid data-lov-depends', e);
        }
        var prefix = select.getAttribute('data-lov-prefix');
        if (prefix === null) {
            var cut = select.name.lastIndexOf('-');
            prefix = cut === -1 ? '' : select.name.substring(0, cut);
        }
        var form = select.form;
        var parentValue = function (name) {
            var full = prefix ? prefix + '-' + name : name;
            var scope = form || document;
            var values = [];
            scope.querySelectorAll('input, select, textarea').forEach(function (field) {
                if (field.name !== full) return;
                if (field.type === 'checkbox' || field.type === 'radio') {
                    if (field.checked) values.push(field.value);
                } else if (field.multiple) {
                    Array.prototype.forEach.call(field.selectedOptions, function (option) {
                        values.push(option.value);
                    });
                } else {
                    values.push(field.value);
                }
            });
            return values.join(',');
        };
        // Out of the form and of any transformed panel: a fixed modal inside a
        // transformed ancestor is drawn inside it, and its inputs have no name.
        document.body.appendChild(modalEl);
        var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        var page = 1;
        var timer = null;
        // A slow answer must not overwrite the one of a later search.
        var request = 0;

        var setValue = function (id, text) {
            select.textContent = '';
            var blank = document.createElement('option');
            blank.value = '';
            select.appendChild(blank);
            if (id !== '' && id !== null && id !== undefined) {
                var option = document.createElement('option');
                option.value = id;
                option.textContent = text;
                option.selected = true;
                select.appendChild(option);
            }
            label.value = text || '';
            select.dispatchEvent(new Event('change', {bubbles: true}));
        };
        var load = function () {
            var current = ++request;
            var query = new URLSearchParams({q: search.value, page: page});
            Object.keys(depends).forEach(function (param) {
                query.append(param, parentValue(depends[param]));
            });
            results.setAttribute('aria-busy', 'true');
            fetch(select.getAttribute('data-url') + '?' + query, {
                credentials: 'same-origin', headers: {'Accept': 'application/json'}
            }).then(function (response) {
                if (!response.ok) throw new Error(response.status);
                return response.json();
            }).then(function (data) {
                if (current !== request) return;
                results.textContent = '';
                (data.results || []).forEach(function (row) {
                    var item = document.createElement('button');
                    item.type = 'button';
                    item.className = 'list-group-item list-group-item-action gt-lov-popup-row';
                    if (String(row.id) === select.value) item.classList.add('active');
                    item.setAttribute('data-value', row.id);
                    item.textContent = row.text;
                    item.addEventListener('click', function () {
                        setValue(row.id, row.text);
                        modal.hide();
                    });
                    results.appendChild(item);
                });
                empty.classList.toggle('d-none', (data.results || []).length > 0);
                prev.disabled = page <= 1;
                next.disabled = !(data.pagination && data.pagination.more);
                pageLabel.textContent = interpolate(gettext('Page %s'), [page]);
            }).catch(function (error) {
                if (current !== request) return;
                results.textContent = '';
                var item = document.createElement('div');
                item.className = 'list-group-item text-danger';
                item.textContent = gettext('The list could not be loaded.');
                results.appendChild(item);
                console.error('LOVPopupSelect', error);
            }).finally(function () {
                if (current === request) results.removeAttribute('aria-busy');
            });
        };

        wrapper.querySelector('.gt-lov-popup-open').addEventListener('click', function () {
            page = 1;
            search.value = '';
            load();
            modal.show();
        });
        modalEl.addEventListener('shown.bs.modal', function () { search.focus(); });
        wrapper.querySelector('.gt-lov-popup-clear').addEventListener('click', function () {
            setValue('', '');
        });
        search.addEventListener('input', function () {
            clearTimeout(timer);
            timer = setTimeout(function () { page = 1; load(); }, 250);
        });
        search.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') { event.preventDefault(); clearTimeout(timer); page = 1; load(); }
        });
        prev.addEventListener('click', function () { if (page > 1) { page--; load(); } });
        next.addEventListener('click', function () { page++; load(); });

        // A parent that changes empties the value, like LOVSelect.
        var parents = Object.keys(depends).map(function (param) {
            return prefix ? prefix + '-' + depends[param] : depends[param];
        });
        if (parents.length && form) {
            form.addEventListener('change', function (event) {
                if (event.target && parents.indexOf(event.target.name) !== -1
                        && select.value) {
                    setValue('', '');
                }
            });
        }
    });
}
