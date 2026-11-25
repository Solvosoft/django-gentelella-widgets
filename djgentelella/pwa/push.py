"""Web push for the notifications of djgentelella.

Every new :class:`~djgentelella.models.Notification` also goes, after the
transaction commits, to the push subscriptions of its user, unless the user
turned push off (:class:`~djgentelella.models.PushPreference`). A subscription
the push service no longer knows (404/410) is deleted.

``send_push(user, payload)`` is public for anything else worth a push.
"""
import binascii
import base64
import json
import logging
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _

from djgentelella.models import PushPreference, PushSubscription
from djgentelella.pwa import conf
from djgentelella.pwa.appsettings import AppSettings
from djgentelella.pwa.backends import PushGone
from djgentelella.sites import site_pk, site_q

logger = logging.getLogger(__name__)


def get_backend():
    """An instance of ``GT_PUSH_BACKEND``."""
    backend = conf.push_backend_path()
    if isinstance(backend, str):
        backend = import_string(backend)
    return backend()


def push_enabled():
    """True when the backend can send: with the default one, the ``[push]``
    extra is installed and the VAPID private key is set."""
    try:
        return get_backend().available()
    except ImportError:
        logger.exception('GT_PUSH_BACKEND cannot be imported')
        return False


def push_wanted(user):
    """The preference of ``user``: True without a row."""
    pref = PushPreference.objects.filter(user=user).values_list(
        'enabled', flat=True).first()
    return True if pref is None else pref


def set_push_wanted(user, enabled):
    PushPreference.objects.update_or_create(
        user=user, defaults={'enabled': bool(enabled)})


def notification_payload(notification, site=None):
    """The push payload of ``notification`` (a dict), titled with the name of
    the application of ``site``."""
    app = AppSettings(site)
    return {
        'title': app.name(),
        'body': notification.description,
        'url': notification.link or conf.scope(),
        'tag': 'gt-notification-%s' % notification.pk,
        'type': notification.message_type,
        'id': notification.pk,
        'icon': app.icon('192'),
    }


def send_push(user, payload, *, site=None, respect_preference=True,
              subscriptions=None):
    """Send ``payload`` to the subscriptions of ``user``; return how many got it.

    ``payload`` is a dict (or a callable ``payload(site)`` giving one, so each
    Site can title it its own way) with ``title``, ``body``, ``url``, ``tag``,
    ``icon``. ``site`` limits the subscriptions to that Site and the global
    ones. A subscription the push service no longer knows is deleted; other
    errors are logged.
    """
    if respect_preference and not push_wanted(user):
        return 0
    backend = get_backend()
    if not backend.available():
        return 0
    if subscriptions is None:
        subscriptions = PushSubscription.objects.filter(user=user)
        if site is not None:
            subscriptions = subscriptions.filter(site_q(site))
        subscriptions = subscriptions.select_related('site')
    sent = 0
    bodies = {}
    for subscription in subscriptions:
        if callable(payload):
            key = subscription.site_id
            if key not in bodies:
                bodies[key] = json.dumps(payload(subscription.site))
            body = bodies[key]
        else:
            body = json.dumps(payload)
        try:
            backend.send(subscription, body)
        except PushGone:
            logger.info('Push subscription %s is gone: deleted', subscription.pk)
            subscription.delete()
            continue
        except Exception:
            logger.exception('Push to subscription %s failed', subscription.pk)
            continue
        PushSubscription.objects.filter(pk=subscription.pk).update(
            last_used=timezone.now())
        sent += 1
    return sent


def push_notification(notification):
    """Send ``notification`` as push to its user's subscriptions."""
    return send_push(
        notification.user,
        lambda site: notification_payload(notification, site))


def on_notification_saved(sender, instance, created, raw=False, **kwargs):
    """``post_save`` of ``Notification``: a new one goes out as push after
    the commit, if push is on."""
    if not created or raw or not push_enabled():
        return
    transaction.on_commit(lambda: push_notification(instance))


# -- subscribing --------------------------------------------------------------

def _b64url(value, field):
    if not isinstance(value, str) or not value or len(value) > 255:
        raise ValidationError(_('Invalid %(field)s.') % {'field': field})
    try:
        base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))
    except (binascii.Error, ValueError):
        raise ValidationError(_('Invalid %(field)s.') % {'field': field})
    return value


def _host_allowed(host):
    allowed = conf.push_hosts()
    if allowed is None:
        return True
    for rule in allowed:
        if rule.startswith('.'):
            if host == rule[1:] or host.endswith(rule):
                return True
        elif host == rule:
            return True
    return False


def clean_subscription(data):
    """Check the JSON of ``PushSubscription.toJSON()``; return
    ``(endpoint, p256dh, auth)`` or raise ``ValidationError``."""
    if not isinstance(data, dict):
        raise ValidationError(_('Invalid subscription.'))
    endpoint = data.get('endpoint')
    keys = data.get('keys') or {}
    if not isinstance(endpoint, str) or len(endpoint) > 1000 \
            or not isinstance(keys, dict):
        raise ValidationError(_('Invalid subscription.'))
    parts = urlsplit(endpoint)
    if parts.scheme != 'https' or not parts.hostname:
        raise ValidationError(_('The endpoint must be an https URL.'))
    if not _host_allowed(parts.hostname.lower()):
        raise ValidationError(
            _('The endpoint is not a known push service.'))
    return (endpoint, _b64url(keys.get('p256dh'), 'p256dh'),
            _b64url(keys.get('auth'), 'auth'))


def subscribe(user, data, *, site=None, user_agent=''):
    """Store the subscription ``data`` of ``user`` (moving it if the endpoint
    was another user's) and return it."""
    endpoint, p256dh, auth = clean_subscription(data)
    subscription, _created = PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={'user': user, 'p256dh': p256dh, 'auth': auth,
                  'site_id': site_pk(site), 'user_agent': user_agent[:500]})
    return subscription


def unsubscribe(user, endpoint):
    """Forget the subscription ``endpoint`` of ``user``; how many went."""
    deleted, _rows = PushSubscription.objects.filter(
        user=user, endpoint=endpoint).delete()
    return deleted
