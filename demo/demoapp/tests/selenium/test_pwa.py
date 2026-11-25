"""W33 in the browser: the service worker registers, caches static files and
nothing else, removes itself when the setting is turned off, and the push
page shows the subscribe button.

Accepting a real push subscription needs the browser's push service (FCM for
Chromium) over the network, which the test browser does not reach: the
subscription itself is covered without a browser in
``djgentelella.tests.PwaPush_Test``. Neither does the offline page: the
network emulation of chromedriver applies to the page, not to the service
worker, so the worker never sees a failed fetch."""
from django.conf import settings
from django.test import override_settings, tag
from django.urls import reverse

from .base import By, EC, SeleniumTestCase

LOCMEM = 'djgentelella.pwa.backends.LocmemPushBackend'

REGISTRATION = """
const done = arguments[arguments.length - 1];
navigator.serviceWorker.getRegistrations().then(function (list) {
    done(list.map(function (r) {
        return {scope: r.scope, active: !!r.active,
                script: r.active ? r.active.scriptURL : null};
    }));
}).catch(function (e) { done('error: ' + e); });
"""

CACHED = """
const done = arguments[arguments.length - 1];
caches.keys().then(function (keys) {
    return Promise.all(keys.map(function (key) {
        return caches.open(key).then(function (cache) {
            return cache.keys().then(function (requests) {
                return {name: key, urls: requests.map(function (r) { return r.url; })};
            });
        });
    }));
}).then(done).catch(function (e) { done('error: ' + e); });
"""

FETCH = """
const done = arguments[arguments.length - 1];
Promise.all(arguments[0].map(function (url) {
    return fetch(url, {credentials: 'same-origin'})
        .then(function (r) { return r.status; });
})).then(done).catch(function (e) { done('error: ' + e); });
"""


@tag('selenium')
@override_settings(GT_PWA_MANIFEST=True, GT_PWA_SERVICE_WORKER=True,
                   GT_PWA_CACHE_VERSION='selenium')
class ServiceWorkerTest(SeleniumTestCase):
    def setUp(self):
        super().setUp()
        self.driver.set_script_timeout(20)

    def tearDown(self):
        # The registration lives in the browser profile, shared by the tests
        # of this class: leave it clean.
        self.driver.execute_async_script("""
            const done = arguments[arguments.length - 1];
            navigator.serviceWorker.getRegistrations().then(function (list) {
                return Promise.all(list.map(function (r) { return r.unregister(); }));
            }).then(function () { return caches.keys(); }).then(function (keys) {
                return Promise.all(keys.map(function (k) { return caches.delete(k); }));
            }).then(function () { done(true); }, function () { done(false); });
        """)
        super().tearDown()

    def registrations(self):
        return self.driver.execute_async_script(REGISTRATION)

    def wait_controlled(self):
        self.wait_js('return window.gt_pwa_registration !== undefined')
        self.wait.until(
            lambda d: any(r['active'] for r in self.registrations()),
            'the service worker never became active')
        # The first page is not controlled until clients.claim(); a reload is.
        self.go(reverse('notification_list'))
        self.wait_js('return !!navigator.serviceWorker.controller',
                     message='the page is not controlled by the service worker')

    def test_the_page_registers_the_service_worker(self):
        self.go(reverse('notification_list'))
        self.assertTrue(self.js(
            "return !!document.querySelector('link[rel=manifest]')"))
        self.wait_controlled()
        registration = self.registrations()[0]
        self.assertTrue(registration['script'].endswith(
            reverse('gt_pwa_service_worker')))
        self.assertEqual(registration['scope'], self.live_server_url + '/')

    def test_only_static_files_are_cached(self):
        self.go(reverse('notification_list'))
        self.wait_controlled()
        static_url = settings.STATIC_URL + 'gentelella/pwa/icon-192.png'
        statuses = self.driver.execute_async_script(FETCH, [
            static_url,
            reverse('api-notificationtable-list') + '?format=json',
            reverse('notification_list'),
            reverse('gt_pwa_manifest'),
        ])
        self.assertEqual(statuses, [200, 200, 200, 200])
        caches = self.driver.execute_async_script(CACHED)
        self.assertEqual([c['name'] for c in caches], ['gt-pwa-selenium'])
        urls = caches[0]['urls']
        offline = self.live_server_url + reverse('gt_pwa_offline')
        self.assertIn(self.live_server_url + static_url, urls)
        self.assertIn(offline, urls)
        static_prefix = self.live_server_url + settings.STATIC_URL
        self.assertEqual(
            [u for u in urls if u != offline and not u.startswith(static_prefix)],
            [])

    def test_turning_the_setting_off_removes_the_worker(self):
        self.go(reverse('notification_list'))
        self.wait_controlled()
        with override_settings(GT_PWA_SERVICE_WORKER=False):
            self.go(reverse('notification_list'))
            self.assertFalse(self.js(
                "return !!document.querySelector('script[data-sw]')"))
            # The browser checks sw.js on navigation; a reg.update() makes it
            # deterministic.
            self.driver.execute_async_script("""
                const done = arguments[arguments.length - 1];
                navigator.serviceWorker.getRegistration().then(function (r) {
                    return r ? r.update() : null;
                }).then(function () { done(true); }, function () { done(true); });
            """)
            self.wait.until(lambda d: self.registrations() == [],
                            'the service worker did not unregister itself')
            self.assertEqual(self.driver.execute_async_script(CACHED), [])


@tag('selenium')
@override_settings(GT_PUSH_BACKEND=LOCMEM)
class PushPreferencesTest(SeleniumTestCase):
    def tearDown(self):
        self.driver.execute_async_script("""
            const done = arguments[arguments.length - 1];
            navigator.serviceWorker.getRegistrations().then(function (list) {
                return Promise.all(list.map(function (r) { return r.unregister(); }));
            }).then(function () { done(true); }, function () { done(false); });
        """)
        super().tearDown()

    def test_the_page_registers_the_worker_and_shows_the_subscribe_button(self):
        self.go(reverse('gt_push_preferences'))
        self.wait_js("return document.getElementById('gt-push-device')"
                     ".dataset.worker === 'ready'",
                     message='the service worker never became ready')
        button = self.wait.until(EC.visibility_of_element_located(
            (By.ID, 'gt-push-subscribe')))
        self.assertTrue(button.is_enabled())
        self.assertFalse(self.driver.find_element(
            By.ID, 'gt-push-unsubscribe').is_displayed())
        self.assertEqual(self.js(
            "return document.getElementById('gt-push-device').dataset.state"),
            'unsubscribed')
