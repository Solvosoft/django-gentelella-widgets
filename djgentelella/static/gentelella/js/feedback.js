/* The feedback button (djgentelella.feedback): fills the page and browser
 * fields only when their boxes are ticked, sends the form with fetch and says
 * how it went. Nothing of the page's own forms is read. */
(function () {
    'use strict';
    var form = document.querySelector('form.gt-feedback-form');
    if (!form || form.dataset.gtReady) {
        return;
    }
    form.dataset.gtReady = '1';
    var result = form.querySelector('.gt-feedback-result');

    function field(name) {
        return form.querySelector('[name="gtfeedback-' + name + '"]');
    }

    function show(kind, text) {
        result.className = 'alert alert-' + kind + ' gt-feedback-result';
        result.textContent = text;
    }

    form.addEventListener('submit', function (event) {
        var withPage = document.getElementById('gt-feedback-with-page').checked;
        var withBrowser = document.getElementById('gt-feedback-with-browser').checked;
        var page = document.querySelector('[data-gtdesign-page]');
        field('url').value = withPage ? window.location.pathname : '';
        field('page').value = withPage && page ? page.getAttribute('data-gtdesign-page') : '';
        field('browser').value = withBrowser ? [navigator.userAgent,
            window.screen.width + 'x' + window.screen.height,
            window.innerWidth + 'x' + window.innerHeight,
            navigator.language].join(' | ') : '';
        if (!window.fetch || !window.FormData) {
            return;  // a plain POST: the server redirects back
        }
        event.preventDefault();
        var button = form.querySelector('.gt-feedback-send');
        button.disabled = true;
        fetch(form.action, {
            method: 'POST', body: new FormData(form), credentials: 'same-origin',
            headers: {'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
        }).then(function (response) {
            return response.json().catch(function () { return {ok: false}; });
        }).then(function (data) {
            button.disabled = false;
            if (data.ok) {
                show('success', data.message);
                field('text').value = '';
                return;
            }
            var errors = [];
            Object.keys(data.errors || {}).forEach(function (key) {
                errors = errors.concat(data.errors[key]);
            });
            show('danger', errors.join(' ') || gettext('The feedback could not be sent.'));
        }).catch(function () {
            button.disabled = false;
            show('danger', gettext('The feedback could not be sent.'));
        });
    });
}());
