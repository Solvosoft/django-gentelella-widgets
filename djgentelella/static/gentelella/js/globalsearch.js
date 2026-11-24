/*
 * The global search box of the top bar (djgentelella.search).
 *
 * Typing asks gtapis/search/ (the form's data-api) and lists the hits under
 * the box, grouped by source; Enter without a highlighted hit submits the form
 * to the results page. Arrow keys move through the hits, Escape closes them.
 * Everything from the server is written with textContent, never as HTML.
 */
(function () {
    'use strict';

    var DELAY = 250;

    function setup(form) {
        if (form.dataset.gtSearchReady) { return; }
        form.dataset.gtSearchReady = '1';
        var input = form.querySelector('input[name="q"]');
        var menu = form.querySelector('.gt-global-search-menu');
        var minLength = parseInt(form.dataset.minLength || '2', 10);
        var timer = null;
        var controller = null;
        var active = -1;

        function items() {
            return Array.prototype.slice.call(menu.querySelectorAll('.gt-global-search-hit'));
        }

        function close() {
            menu.classList.remove('show');
            input.setAttribute('aria-expanded', 'false');
            active = -1;
        }

        function open() {
            menu.classList.add('show');
            input.setAttribute('aria-expanded', 'true');
        }

        function highlight(index) {
            var list = items();
            list.forEach(function (item, i) {
                item.classList.toggle('active', i === index);
                item.setAttribute('aria-selected', i === index ? 'true' : 'false');
            });
            active = index;
            if (list[index]) { list[index].scrollIntoView({block: 'nearest'}); }
        }

        function render(data) {
            menu.textContent = '';
            if (!data.groups.length) {
                var empty = document.createElement('span');
                empty.className = 'dropdown-item-text text-muted';
                empty.textContent = menu.dataset.empty;
                menu.appendChild(empty);
            }
            data.groups.forEach(function (group) {
                var header = document.createElement('h6');
                header.className = 'dropdown-header';
                if (group.icon) {
                    var icon = document.createElement('i');
                    icon.className = group.icon;
                    icon.setAttribute('aria-hidden', 'true');
                    header.appendChild(icon);
                    header.appendChild(document.createTextNode(' '));
                }
                header.appendChild(document.createTextNode(group.label));
                menu.appendChild(header);
                group.results.forEach(function (hit) {
                    var item = document.createElement(hit.url ? 'a' : 'span');
                    item.className = 'dropdown-item gt-global-search-hit';
                    item.setAttribute('role', 'option');
                    item.dataset.source = group.source;
                    if (hit.url) { item.href = hit.url; }
                    var title = document.createElement('div');
                    title.textContent = hit.title;
                    item.appendChild(title);
                    if (hit.subtitle) {
                        var subtitle = document.createElement('small');
                        subtitle.className = 'text-muted';
                        subtitle.textContent = hit.subtitle;
                        item.appendChild(subtitle);
                    }
                    menu.appendChild(item);
                });
                if (group.has_more) {
                    var more = document.createElement('a');
                    more.className = 'dropdown-item small gt-global-search-more';
                    more.href = group.more_url;
                    more.textContent = menu.dataset.more + ' »';
                    menu.appendChild(more);
                }
            });
            active = -1;
            open();
        }

        function lookup() {
            var text = input.value.trim();
            if (text.length < minLength) { close(); return; }
            if (controller) { controller.abort(); }
            controller = window.AbortController ? new AbortController() : null;
            var url = form.dataset.api + '?' + new URLSearchParams({q: text});
            fetch(url, {
                credentials: 'same-origin',
                headers: {'Accept': 'application/json'},
                signal: controller ? controller.signal : undefined
            }).then(function (response) {
                if (!response.ok) { throw new Error(response.status); }
                return response.json();
            }).then(function (data) {
                // An answer that arrives after the text changed is stale.
                if (data.query === input.value.trim().split(/\s+/).join(' ')) {
                    render(data);
                }
            }).catch(function () { /* aborted or failed: keep what is shown */ });
        }

        input.addEventListener('input', function () {
            clearTimeout(timer);
            timer = setTimeout(lookup, DELAY);
        });
        input.addEventListener('keydown', function (event) {
            var list = items();
            if (event.key === 'ArrowDown' && list.length) {
                event.preventDefault();
                open();
                highlight(Math.min(active + 1, list.length - 1));
            } else if (event.key === 'ArrowUp' && list.length) {
                event.preventDefault();
                highlight(Math.max(active - 1, 0));
            } else if (event.key === 'Escape') {
                close();
            } else if (event.key === 'Enter' && active >= 0 && list[active]
                       && list[active].href) {
                event.preventDefault();
                window.location.href = list[active].href;
            }
        });
        input.addEventListener('focus', function () {
            if (menu.childNodes.length && input.value.trim().length >= minLength) { open(); }
        });
        document.addEventListener('click', function (event) {
            if (!form.contains(event.target)) { close(); }
        });
    }

    function init() {
        document.querySelectorAll('.gt-global-search-form').forEach(setup);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
