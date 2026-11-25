/* The push page of djgentelella.pwa: subscribe this browser, unsubscribe it,
 * send a test. The URLs and the VAPID public key come in the data- attributes
 * of #gt-push-device. */
(function () {
    'use strict';
    var box = document.getElementById('gt-push-device');
    if (!box) { return; }
    var _ = window.gettext || function (text) { return text; };
    var status = document.getElementById('gt-push-status');
    var subscribeBtn = document.getElementById('gt-push-subscribe');
    var unsubscribeBtn = document.getElementById('gt-push-unsubscribe');
    var testBtn = document.getElementById('gt-push-test');

    function csrftoken() {
        var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function post(url, data) {
        return fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrftoken()},
            body: JSON.stringify(data || {})
        }).then(function (response) {
            return response.json().catch(function () { return {}; }).then(function (body) {
                if (!response.ok) { throw new Error(body.detail || response.statusText); }
                return body;
            });
        });
    }

    function keyBytes(base64url) {
        var padded = (base64url + '===='.slice(base64url.length % 4 || 4))
            .replace(/-/g, '+').replace(/_/g, '/');
        var raw = window.atob(padded);
        var bytes = new Uint8Array(raw.length);
        for (var i = 0; i < raw.length; i++) { bytes[i] = raw.charCodeAt(i); }
        return bytes;
    }

    function show(subscribed) {
        box.dataset.state = subscribed ? 'subscribed' : 'unsubscribed';
        subscribeBtn.classList.toggle('d-none', subscribed);
        unsubscribeBtn.classList.toggle('d-none', !subscribed);
        testBtn.classList.toggle('d-none', !subscribed);
        status.textContent = subscribed
            ? _('This device receives your push notifications.')
            : _('This device does not receive push notifications.');
    }

    function fail(error) {
        status.textContent = _('Push notifications failed:') + ' ' + (error && error.message || error);
        box.dataset.error = String(error && error.message || error);
    }

    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
        status.textContent = _('This browser does not support push notifications.');
        box.dataset.state = 'unsupported';
        return;
    }

    var ready = navigator.serviceWorker.register(box.dataset.sw, {scope: box.dataset.scope || '/'})
        .then(function () { return navigator.serviceWorker.ready; });

    ready.then(function (registration) {
        box.dataset.worker = 'ready';
        return registration.pushManager.getSubscription();
    }).then(function (subscription) {
        show(!!subscription);
        if (subscription) {
            // The server may have forgotten it (a logout with
            // GT_PUSH_UNSUBSCRIBE_ON_LOGOUT): storing it again is harmless.
            post(box.dataset.subscribe, subscription.toJSON()).catch(function () {});
        }
        if (Notification.permission === 'denied') {
            status.textContent = _('This browser blocks the notifications of this site.');
        }
    }).catch(fail);

    subscribeBtn.addEventListener('click', function () {
        Notification.requestPermission().then(function (permission) {
            if (permission !== 'granted') {
                throw new Error(_('permission not granted'));
            }
            return ready;
        }).then(function (registration) {
            return registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: keyBytes(box.dataset.key)
            });
        }).then(function (subscription) {
            return post(box.dataset.subscribe, subscription.toJSON());
        }).then(function () { show(true); }).catch(fail);
    });

    unsubscribeBtn.addEventListener('click', function () {
        ready.then(function (registration) {
            return registration.pushManager.getSubscription();
        }).then(function (subscription) {
            if (!subscription) { return null; }
            var endpoint = subscription.endpoint;
            return subscription.unsubscribe().then(function () {
                return post(box.dataset.unsubscribe, {endpoint: endpoint});
            });
        }).then(function () { show(false); }).catch(fail);
    });

    testBtn.addEventListener('click', function () {
        post(box.dataset.test).then(function (body) {
            status.textContent = interpolate(
                _('Test sent to %s device(s).'), [body.sent]);
        }).catch(fail);
    });

    function interpolate(text, values) {
        if (window.interpolate) { return window.interpolate(text, values); }
        return text.replace('%s', values[0]);
    }
})();
