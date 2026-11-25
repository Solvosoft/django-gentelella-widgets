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

from django.conf import settings
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
        'url': notification.link or app.scope(),
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


def queued():
    """Whether new notifications go out through Celery (``GT_PUSH_QUEUE``)."""
    mode = conf.push_queue()
    if mode == 'celery':
        return True
    if mode == 'auto':
        # The rule of djgentelella.async_notification's dispatch backend.
        try:
            import celery  # noqa: F401,PLC0415 optional dependency
        except ImportError:
            return False
        return bool(getattr(settings, 'CELERY_BROKER_URL', None))
    return False


def dispatch_notification(notification):
    """Send ``notification`` as push now, or queue it (:func:`queued`)."""
    if queued():
        # Defined only when Celery is installed.
        from djgentelella.pwa.tasks import push_notification_task  # noqa: PLC0415
        push_notification_task.delay(notification.pk)
        return None
    return push_notification(notification)


def on_notification_saved(sender, instance, created, raw=False, **kwargs):
    """``post_save`` of ``Notification``: a new one goes out as push after
    the commit, if push is on: sent there or queued (``GT_PUSH_QUEUE``)."""
    if not created or raw or not push_enabled():
        return
    transaction.on_commit(lambda: dispatch_notification(instance))


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


def resubscribe(old, data):
    """``pushsubscriptionchange``: the browser replaced the subscription
    ``old`` (``{endpoint, keys: {auth}}``, its ``toJSON()``) by ``data``. The
    old one proves who asks -- its ``auth`` secret only the browser and the
    server know --, so no session is needed. Returns the subscription, or
    ``None`` when ``old`` is not known."""
    if not isinstance(old, dict):
        raise ValidationError(_('Invalid subscription.'))
    keys = old.get('keys') if isinstance(old.get('keys'), dict) else {}
    endpoint, auth = old.get('endpoint'), keys.get('auth')
    if not isinstance(endpoint, str) or not isinstance(auth, str) or not auth:
        raise ValidationError(_('Invalid subscription.'))
    found = PushSubscription.objects.filter(endpoint=endpoint, auth=auth).first()
    if found is None:
        return None
    new_endpoint, p256dh, new_auth = clean_subscription(data)
    with transaction.atomic():
        # The new endpoint may already be stored (two tabs, a retry).
        PushSubscription.objects.filter(endpoint=new_endpoint).exclude(
            pk=found.pk).delete()
        found.endpoint, found.p256dh, found.auth = new_endpoint, p256dh, new_auth
        found.save(update_fields=['endpoint', 'p256dh', 'auth'])
    return found


SESSION_KEY = 'gt_push_endpoints'


def remember_in_session(request, endpoint):
    """Note that this browser's session subscribed ``endpoint``: what
    ``GT_PUSH_UNSUBSCRIBE_ON_LOGOUT`` forgets on logout."""
    session = getattr(request, 'session', None)
    if session is None:
        return
    endpoints = [item for item in session.get(SESSION_KEY, []) if item != endpoint]
    session[SESSION_KEY] = (endpoints + [endpoint])[-10:]


def on_user_logged_out(sender, request=None, user=None, **kwargs):
    """``user_logged_out``: with ``GT_PUSH_UNSUBSCRIBE_ON_LOGOUT``, forget
    the subscriptions this session registered (only the user's)."""
    if not conf.unsubscribe_on_logout() or user is None or request is None:
        return
    session = getattr(request, 'session', None)
    endpoints = session.get(SESSION_KEY, []) if session is not None else []
    if endpoints:
        PushSubscription.objects.filter(user=user, endpoint__in=endpoints).delete()


def unsubscribe(user, endpoint):
    """Forget the subscription ``endpoint`` of ``user``; how many went."""
    deleted, _rows = PushSubscription.objects.filter(
        user=user, endpoint=endpoint).delete()
    return deleted
