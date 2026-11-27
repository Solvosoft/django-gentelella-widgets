"""W33: manifest per Site, service worker and web push of the notifications
(djgentelella.pwa). No network: the push backend is LocmemPushBackend or a
mocked pywebpush."""
import io
import json
import re
import sys
from unittest import mock, skipUnless

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import (
    Client, RequestFactory, TestCase, TransactionTestCase, override_settings,
)
from django.urls import reverse

from djgentelella.models import (
    Notification, PushPreference, PushSubscription, push_endpoint_hash,
)
from djgentelella.notification import create_notification
from djgentelella.pwa import backends, push
from djgentelella.pwa.appsettings import AppSettings
from djgentelella.pwa.backends import LocmemPushBackend, PushGone
from djgentelella.pwa.manifest import worker_config
from djgentelella.templatetags.gtpwa import pwa_head
from djgentelella.utils import set_settings

try:
    import pywebpush
except ImportError:                                   # pragma: no cover
    pywebpush = None

__all__ = [
    'W33ManifestTests', 'W33ServiceWorkerTests', 'W33SubscriptionTests',
    'W33PushSendingTests', 'W33WebPushBackendTests', 'W33WithoutExtraTests',
    'W33PreferencesTests', 'W33EndpointHashMigrationTests',
]

LOCMEM = 'djgentelella.pwa.backends.LocmemPushBackend'
FCM = 'https://fcm.googleapis.com/fcm/send/abc123'
P256DH = ('BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1Xbjh'
          'azAkj7I99e8QcYP7DkM')
AUTH = 'tBHItJI5svbpez7KI4CCXg'


def subscription_json(endpoint=FCM, p256dh=P256DH, auth=AUTH):
    return {'endpoint': endpoint, 'keys': {'p256dh': p256dh, 'auth': auth}}


class PushTestMixin:
    def setUp(self):
        super().setUp()
        LocmemPushBackend.outbox = []
        LocmemPushBackend.gone = set()
        self.user = get_user_model().objects.create_user(
            'pushuser', 'push@example.com', 'secret')
        self.client.force_login(self.user)

    def post_json(self, name, data, client=None):
        return (client or self.client).post(
            reverse(name), json.dumps(data), content_type='application/json')

    def add_subscription(self, endpoint=FCM, user=None, site=None):
        return PushSubscription.objects.create(
            user=user or self.user, endpoint=endpoint, p256dh=P256DH, auth=AUTH,
            site=site)


class W33ManifestTests(TestCase):
    def setUp(self):
        self.site = Site.objects.create(domain='app2.example', name='Second app')

    def manifest(self, host='testserver'):
        response = self.client.get(reverse('gt_pwa_manifest'), HTTP_HOST=host)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/manifest+json')
        return json.loads(response.content)

    @override_settings(ALLOWED_HOSTS=['*'])
    def test_manifest_takes_the_settings_of_the_site(self):
        set_settings('site_title', 'Global title')
        set_settings('pwa_name', 'App Two', site=self.site)
        set_settings('pwa_short_name', 'Two', site=self.site)
        set_settings('pwa_theme_color', '#112233', site=self.site)
        set_settings('pwa_icon_192', '/media/two-192.png', site=self.site)
        global_ = self.manifest()
        self.assertEqual(global_['name'], 'Global title')
        self.assertEqual(global_['short_name'], 'Global title')
        self.assertEqual(global_['theme_color'], '#2A3F54')
        self.assertTrue(global_['icons'][0]['src'].endswith(
            'gentelella/pwa/icon-192.png'))
        self.assertEqual(global_['display'], 'standalone')
        self.assertEqual(global_['start_url'], '/')
        site = self.manifest('app2.example')
        self.assertEqual(site['name'], 'App Two')
        self.assertEqual(site['short_name'], 'Two')
        self.assertEqual(site['theme_color'], '#112233')
        self.assertEqual(site['icons'][0]['src'], '/media/two-192.png')
        self.assertEqual(site['icons'][1]['sizes'], '512x512')

    @override_settings(ALLOWED_HOSTS=['*'])
    def test_manifest_falls_back_to_the_site_name(self):
        set_settings('site_title', '')
        self.assertEqual(self.manifest('app2.example')['name'], 'Second app')

    def test_the_settings_of_an_app_cost_one_query(self):
        set_settings('pwa_name', 'Global')
        set_settings('pwa_name', '', site=self.site)
        set_settings('pwa_theme_color', '#000000', site=self.site)
        with self.assertNumQueries(1):
            app = AppSettings(self.site)
        self.assertEqual((app.name(), app.get('pwa_theme_color')),
                         ('Global', '#000000'))
        # Cached for every Site, and forgotten when a setting is saved.
        with self.assertNumQueries(0):
            self.assertEqual(AppSettings().name(), 'Global')
            self.assertEqual(AppSettings(self.site).get('pwa_theme_color'), '#000000')
        set_settings('pwa_theme_color', '#ffffff', site=self.site)
        self.assertEqual(AppSettings(self.site).get('pwa_theme_color'), '#ffffff')

    @override_settings(GT_PWA_MANIFEST=True, GT_PWA_SERVICE_WORKER=True)
    def test_the_head_of_a_page_costs_no_query_once_cached(self):
        set_settings('pwa_scope', '/app/', site=self.site)
        AppSettings(self.site)
        request = RequestFactory().get('/')
        request.site = self.site
        with self.assertNumQueries(0):
            content = pwa_head({'request': request})
        self.assertIn('rel="manifest"', content)
        self.assertIn('data-scope="/app/"', content)

    def page(self, host='testserver'):
        user = get_user_model().objects.create_user('pageuser', password='x')
        self.client.force_login(user)
        return self.client.get(reverse('notification_list'), HTTP_HOST=host)

    @override_settings(GT_PWA_MANIFEST=False, GT_PWA_SERVICE_WORKER=False)
    def test_tags_are_off_without_the_settings(self):
        content = self.page().content.decode()
        self.assertNotIn('rel="manifest"', content)
        self.assertNotIn('pwa/register.js', content)

    @override_settings(GT_PWA_MANIFEST=True, ALLOWED_HOSTS=['*'])
    def test_manifest_tags_behind_the_setting(self):
        set_settings('pwa_theme_color', '#445566', site=self.site)
        content = self.page('app2.example').content.decode()
        self.assertIn('<link rel="manifest" href="%s">' % reverse('gt_pwa_manifest'),
                      content)
        self.assertIn('<meta name="theme-color" content="#445566">', content)
        self.assertNotIn('pwa/register.js', content)

    @override_settings(GT_PWA_SERVICE_WORKER=True, GT_PWA_MANIFEST=False)
    def test_registration_behind_its_setting(self):
        content = self.page().content.decode()
        self.assertIn('gentelella/js/pwa/register.js', content)
        self.assertIn('data-sw="%s"' % reverse('gt_pwa_service_worker'), content)
        self.assertNotIn('rel="manifest"', content)


class W33ServiceWorkerTests(PushTestMixin, TestCase):
    def worker(self):
        response = self.client.get(reverse('gt_pwa_service_worker'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/javascript')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['Service-Worker-Allowed'], '/')
        match = re.search(r'var GT_PWA = (\{.*?\});\n', response.content.decode())
        return json.loads(match.group(1))

    @override_settings(GT_PWA_SERVICE_WORKER=True)
    def test_the_worker_caches_static_files_only(self):
        config = self.worker()
        self.assertEqual(config['mode'], 'cache')
        self.assertEqual(config['cache_prefixes'], [settings.STATIC_URL])
        self.assertEqual(config['offline_url'], reverse('gt_pwa_offline'))
        apis = [reverse('api-notificationtable-list'), reverse('gt_push_subscribe'),
                reverse('gt-lov', args=['x']), '/api/trash/', '/gtapis/',
                reverse('notification_list'), reverse('gt_pwa_manifest')]
        for url in apis:
            self.assertFalse(
                any(url.startswith(prefix) for prefix in config['cache_prefixes']),
                url)
        self.assertFalse(config['push'])

    @override_settings(GT_PWA_SERVICE_WORKER=True, GT_PWA_CACHE_VERSION='v9',
                       GT_PWA_CACHE_URLS=['/media/public/'],
                       GT_PWA_PRECACHE=['gentelella/pwa/icon-192.png'])
    def test_the_cache_is_versioned_and_extensible(self):
        config = self.worker()
        self.assertEqual(config['cache_name'], 'gt-pwa-v9')
        self.assertEqual(config['cache_prefixes'],
                         [settings.STATIC_URL, '/media/public/'])
        self.assertTrue(config['precache'][0].endswith('gentelella/pwa/icon-192.png'))

    def test_turned_off_the_worker_removes_itself(self):
        config = self.worker()
        self.assertEqual(config['mode'], 'remove')
        self.assertEqual(config['cache_prefixes'], [])

    @override_settings(GT_PUSH_BACKEND=LOCMEM)
    def test_push_alone_keeps_a_push_only_worker(self):
        config = self.worker()
        self.assertEqual(config['mode'], 'push')
        self.assertTrue(config['push'])
        self.assertEqual(config['cache_prefixes'], [])

    def test_the_offline_page_needs_no_login(self):
        self.client.logout()
        response = self.client.get(reverse('gt_pwa_offline'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'gt-pwa-offline')


@override_settings(GT_PUSH_BACKEND=LOCMEM)
class W33SubscriptionTests(PushTestMixin, TestCase):
    @override_settings(ALLOWED_HOSTS=['*'])
    def test_subscribe_and_unsubscribe(self):
        site = Site.objects.create(domain='app3.example', name='Third')
        response = self.client.post(
            reverse('gt_push_subscribe'), json.dumps(subscription_json()),
            content_type='application/json', HTTP_HOST='app3.example',
            HTTP_USER_AGENT='Firefox test')
        self.assertEqual(response.status_code, 201)
        subscription = PushSubscription.objects.get()
        self.assertEqual((subscription.user, subscription.site, subscription.p256dh,
                          subscription.auth, subscription.user_agent),
                         (self.user, site, P256DH, AUTH, 'Firefox test'))
        response = self.post_json('gt_push_unsubscribe', {'endpoint': FCM})
        self.assertEqual(response.json(), {'deleted': 1})
        self.assertFalse(PushSubscription.objects.exists())

    def test_subscribing_again_updates_and_moves_the_endpoint(self):
        other = get_user_model().objects.create_user('other', password='x')
        self.add_subscription(user=other)
        self.assertEqual(self.post_json('gt_push_subscribe',
                                        subscription_json()).status_code, 201)
        self.assertEqual(PushSubscription.objects.get().user, self.user)

    def test_the_uniqueness_is_the_hash_of_the_endpoint(self):
        # MySQL refuses a unique index over a 1000 character column
        # (error 1071): the endpoint has none, its sha256 is the unique one.
        self.assertFalse(PushSubscription._meta.get_field('endpoint').unique)
        self.assertTrue(PushSubscription._meta.get_field('endpoint_hash').unique)
        long = FCM + '/' + 'x' * (1000 - len(FCM) - 1)
        self.assertEqual(self.post_json('gt_push_subscribe', subscription_json(
            endpoint=long)).status_code, 201)
        subscription = PushSubscription.objects.get()
        self.assertEqual(subscription.endpoint_hash, push_endpoint_hash(long))
        with self.assertRaises(IntegrityError), transaction.atomic():
            PushSubscription.objects.bulk_create([PushSubscription(
                user=self.user, endpoint=long, endpoint_hash=push_endpoint_hash(long),
                p256dh=P256DH, auth=AUTH)])
        self.assertEqual(push.unsubscribe(self.user, long), 1)

    def test_unsubscribe_only_touches_own_subscriptions(self):
        other = get_user_model().objects.create_user('other', password='x')
        self.add_subscription(user=other)
        response = self.post_json('gt_push_unsubscribe', {'endpoint': FCM})
        self.assertEqual(response.json(), {'deleted': 0})
        self.assertTrue(PushSubscription.objects.exists())

    def test_invalid_subscriptions_are_refused(self):
        for data in (
                subscription_json(endpoint='http://fcm.googleapis.com/x'),
                subscription_json(endpoint='https://127.0.0.1/internal'),
                subscription_json(endpoint='https://evil.example/fcm.googleapis.com'),
                subscription_json(endpoint='https://evilgoogle.com/fcm/send/x'),
                subscription_json(p256dh='not base64 !'),
                subscription_json(auth=''),
                {'endpoint': FCM}, ['x'], 'x'):
            response = self.post_json('gt_push_subscribe', data)
            self.assertEqual(response.status_code, 400, data)
        self.assertFalse(PushSubscription.objects.exists())

    def test_push_services_of_the_browsers_are_accepted(self):
        for endpoint in ('https://updates.push.services.mozilla.com/wpush/v2/x',
                         'https://jmt17.google.com/fcm/send/x',
                         'https://web.push.apple.com/QGx',
                         'https://wns2-par02p.notify.windows.com/w/?token=x'):
            self.assertEqual(self.post_json(
                'gt_push_subscribe', subscription_json(endpoint)).status_code,
                201, endpoint)

    @override_settings(GT_PUSH_ALLOWED_HOSTS=None)
    def test_the_host_list_can_be_turned_off(self):
        self.assertEqual(self.post_json('gt_push_subscribe', subscription_json(
            'https://push.example.org/x')).status_code, 201)

    def test_anonymous_gets_403(self):
        self.client.logout()
        for name in ('gt_push_subscribe', 'gt_push_unsubscribe', 'gt_push_test'):
            self.assertEqual(self.post_json(name, subscription_json()).status_code,
                             403, name)

    def test_csrf_is_enforced(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = self.post_json('gt_push_subscribe', subscription_json(),
                                  client=client)
        self.assertEqual(response.status_code, 403)

    def test_only_post(self):
        self.assertEqual(self.client.get(reverse('gt_push_subscribe')).status_code,
                         405)


@override_settings(GT_PUSH_BACKEND=LOCMEM)
class W33PushSendingTests(PushTestMixin, TestCase):
    def test_a_new_notification_goes_to_the_backend(self):
        site = Site.objects.create(domain='app4.example', name='Fourth')
        set_settings('site_title', 'Global app')
        set_settings('pwa_name', 'Fourth app', site=site)
        self.add_subscription()
        self.add_subscription('https://fcm.googleapis.com/fcm/send/second', site=site)
        with self.captureOnCommitCallbacks(execute=True):
            notification = create_notification(
                'Your report is ready', self.user, 'success',
                link='https://example.com/report/1')
        self.assertEqual(len(LocmemPushBackend.outbox), 2)
        by_endpoint = {m['endpoint']: json.loads(m['payload'])
                       for m in LocmemPushBackend.outbox}
        payload = by_endpoint[FCM]
        self.assertEqual(payload, {
            'title': 'Global app',
            'body': 'Your report is ready',
            'url': 'https://example.com/report/1',
            'tag': 'gt-notification-%s' % notification.pk,
            'type': 'success',
            'id': notification.pk,
            'icon': payload['icon'],
        })
        self.assertTrue(payload['icon'].endswith('gentelella/pwa/icon-192.png'))
        self.assertEqual(
            by_endpoint['https://fcm.googleapis.com/fcm/send/second']['title'],
            'Fourth app')
        self.assertEqual(LocmemPushBackend.outbox[0]['subscription']['keys'],
                         {'p256dh': P256DH, 'auth': AUTH})
        self.assertIsNotNone(PushSubscription.objects.get(endpoint=FCM).last_used)

    def test_nothing_is_sent_before_the_commit_or_for_an_update(self):
        self.add_subscription()
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            notification = Notification.objects.create(
                user=self.user, description='x', link='https://e.com',
                message_type='info')
        self.assertEqual(LocmemPushBackend.outbox, [])
        self.assertEqual(len(callbacks), 1)
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            notification.state = 'hide'
            notification.save()
        self.assertEqual(callbacks, [])

    def test_the_preference_of_the_user_is_respected(self):
        self.add_subscription()
        PushPreference.objects.create(user=self.user, enabled=False)
        with self.captureOnCommitCallbacks(execute=True):
            create_notification('x', self.user, 'info', link='https://e.com')
        self.assertEqual(LocmemPushBackend.outbox, [])

    def test_only_the_subscriptions_of_the_user(self):
        other = get_user_model().objects.create_user('other', password='x')
        self.add_subscription(user=other)
        with self.captureOnCommitCallbacks(execute=True):
            create_notification('x', self.user, 'info', link='https://e.com')
        self.assertEqual(LocmemPushBackend.outbox, [])

    def test_a_gone_subscription_is_deleted(self):
        self.add_subscription()
        kept = self.add_subscription('https://fcm.googleapis.com/fcm/send/kept')
        LocmemPushBackend.gone = {FCM}
        with self.captureOnCommitCallbacks(execute=True):
            create_notification('x', self.user, 'info', link='https://e.com')
        self.assertEqual(list(PushSubscription.objects.all()), [kept])
        self.assertEqual(len(LocmemPushBackend.outbox), 1)

    def test_another_error_keeps_the_subscription_and_the_notification(self):
        self.add_subscription()
        with mock.patch.object(LocmemPushBackend, 'send',
                               side_effect=RuntimeError('down')), \
                self.assertLogs('djgentelella.pwa.push', 'ERROR'), \
                self.captureOnCommitCallbacks(execute=True):
            create_notification('x', self.user, 'info', link='https://e.com')
        self.assertTrue(PushSubscription.objects.exists())
        self.assertTrue(Notification.objects.exists())

    def test_send_push_limited_to_a_site(self):
        site = Site.objects.create(domain='app5.example', name='Fifth')
        other_site = Site.objects.create(domain='app6.example', name='Sixth')
        self.add_subscription('https://fcm.googleapis.com/fcm/send/global')
        self.add_subscription('https://fcm.googleapis.com/fcm/send/5', site=site)
        self.add_subscription('https://fcm.googleapis.com/fcm/send/6', site=other_site)
        sent = push.send_push(self.user, {'title': 't', 'body': 'b'}, site=site)
        self.assertEqual(sent, 2)
        self.assertEqual(sorted(m['endpoint'][-6:] for m in LocmemPushBackend.outbox),
                         ['global', 'send/5'])

    def test_the_test_button_sends_to_every_device(self):
        self.add_subscription()
        PushPreference.objects.create(user=self.user, enabled=False)
        response = self.post_json('gt_push_test', {})
        self.assertEqual(response.json(), {'sent': 1})
        self.assertEqual(json.loads(LocmemPushBackend.outbox[0]['payload'])['tag'],
                         'gt-push-test')


@skipUnless(pywebpush, 'the [push] extra (pywebpush) is not installed')
class W33WebPushBackendTests(PushTestMixin, TestCase):
    def keys(self):
        out = io.StringIO()
        call_command('gt_vapid_keys', stdout=out)
        values = dict(re.findall(r"(GT_PUSH_VAPID_\w+) = '([^']+)'", out.getvalue()))
        return values['GT_PUSH_VAPID_PRIVATE_KEY'], values['GT_PUSH_VAPID_PUBLIC_KEY']

    def test_available_only_with_the_private_key(self):
        self.assertFalse(backends.WebPushBackend().available())
        private, public = self.keys()
        with override_settings(GT_PUSH_VAPID_PRIVATE_KEY=private):
            backend = backends.WebPushBackend()
            self.assertTrue(backend.available())
            self.assertEqual(backend.application_server_key(), public)

    def test_sends_with_vapid_and_maps_410_to_gone(self):
        private, _public = self.keys()
        subscription = self.add_subscription()
        with override_settings(GT_PUSH_VAPID_PRIVATE_KEY=private,
                               GT_PUSH_VAPID_SUBJECT='mailto:ops@example.com',
                               GT_PUSH_TTL=60), \
                mock.patch.object(pywebpush, 'webpush') as webpush:
            backends.WebPushBackend().send(subscription, '{"body": "x"}')
            kwargs = webpush.call_args.kwargs
            self.assertEqual(kwargs['subscription_info'],
                             subscription.subscription_info())
            self.assertEqual(kwargs['data'], '{"body": "x"}')
            self.assertEqual(kwargs['vapid_claims'], {'sub': 'mailto:ops@example.com'})
            self.assertEqual(kwargs['ttl'], 60)
            self.assertEqual(backends.public_key_of(private), _public)
            for status, expected in ((410, PushGone), (404, PushGone),
                                     (500, pywebpush.WebPushException)):
                webpush.side_effect = pywebpush.WebPushException(
                    'failed', response=mock.Mock(status_code=status))
                with self.assertRaises(expected):
                    backends.WebPushBackend().send(subscription, '{}')

    def test_410_from_the_push_service_deletes_the_subscription(self):
        private, _public = self.keys()
        self.add_subscription()
        with override_settings(GT_PUSH_VAPID_PRIVATE_KEY=private), \
                mock.patch.object(pywebpush, 'webpush', side_effect=(
                    pywebpush.WebPushException(
                        'gone', response=mock.Mock(status_code=410)))), \
                self.captureOnCommitCallbacks(execute=True):
            create_notification('x', self.user, 'info', link='https://e.com')
        self.assertFalse(PushSubscription.objects.exists())

    def test_pem_keys_are_accepted(self):
        from cryptography.hazmat.primitives import serialization  # noqa: PLC0415 -- optional dependency, the [push] extra
        from cryptography.hazmat.primitives.asymmetric import ec  # noqa: PLC0415 -- optional dependency, the [push] extra
        pem = ec.generate_private_key(ec.SECP256R1()).private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()).decode()
        self.assertEqual(len(backends.public_key_of(pem)), 87)


class W33WithoutExtraTests(PushTestMixin, TestCase):
    """Default backend, and pywebpush cannot be imported."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(sys.modules, {'pywebpush': None})
        patcher.start()
        self.addCleanup(patcher.stop)

    @override_settings(GT_PUSH_VAPID_PRIVATE_KEY='somekey')
    def test_everything_works_without_push(self):
        self.assertFalse(push.push_enabled())
        self.add_subscription()
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            create_notification('x', self.user, 'info', link='https://e.com')
        self.assertEqual(callbacks, [])
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(self.post_json('gt_push_subscribe',
                                        subscription_json()).status_code, 503)
        self.assertEqual(self.post_json('gt_push_test', {}).status_code, 503)
        page = self.client.get(reverse('gt_push_preferences'))
        self.assertContains(page, 'gt-push-unavailable')
        self.assertNotContains(page, 'gt-push-subscribe')
        self.assertEqual(worker_config(None)['mode'], 'remove')
        self.assertEqual(push.send_push(self.user, {'title': 'x'}), 0)


@override_settings(GT_PUSH_BACKEND=LOCMEM)
class W33PreferencesTests(PushTestMixin, TestCase):
    def test_the_page_shows_the_subscribe_button(self):
        response = self.client.get(reverse('gt_push_preferences'))
        self.assertContains(response, 'id="gt-push-subscribe"')
        self.assertContains(response, 'data-key="%s"'
                            % LocmemPushBackend().application_server_key())
        self.assertContains(response, 'gentelella/js/pwa/push.js')

    def test_the_page_needs_a_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('gt_push_preferences')).status_code,
                         302)

    def test_turning_push_off_and_on(self):
        self.assertTrue(push.push_wanted(self.user))
        self.client.post(reverse('gt_push_preferences'), {})
        self.assertFalse(push.push_wanted(self.user))
        self.client.post(reverse('gt_push_preferences'), {'enabled': '1'})
        self.assertTrue(push.push_wanted(self.user))
        self.assertEqual(PushPreference.objects.count(), 1)


class W33EndpointHashMigrationTests(TransactionTestCase):
    """0029 gives the subscriptions stored before it their hash."""

    def test_existing_rows_get_their_hash(self):
        executor = MigrationExecutor(connection)
        before, after = [('djgentelella', '0028_translations')], [
            ('djgentelella', '0029_push_endpoint_hash')]
        executor.migrate(before)
        old_apps = executor.loader.project_state(before).apps
        user = old_apps.get_model(*settings.AUTH_USER_MODEL.split('.')).objects.create(
            username='before')
        old_apps.get_model('djgentelella', 'PushSubscription').objects.create(
            user_id=user.pk, endpoint=FCM, p256dh=P256DH, auth=AUTH)
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(after)
        self.assertEqual(PushSubscription.objects.get().endpoint_hash,
                         push_endpoint_hash(FCM))
