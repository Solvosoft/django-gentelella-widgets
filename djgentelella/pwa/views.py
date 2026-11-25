"""Manifest, service worker, offline page and the push endpoints."""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from djgentelella.models import PushSubscription
from djgentelella.pwa import conf, push
from djgentelella.pwa.appsettings import AppSettings
from djgentelella.pwa.manifest import build_manifest, worker_config
from djgentelella.sites import get_current_site


@require_GET
def manifest_view(request):
    """The web app manifest of the current Site."""
    response = JsonResponse(build_manifest(request),
                            json_dumps_params={'ensure_ascii': False})
    response['Content-Type'] = 'application/manifest+json'
    response['Cache-Control'] = 'no-cache'
    return response


@require_GET
def service_worker_view(request):
    """``sw.js``. Allowed to control ``GT_PWA_SCOPE`` wherever it is mounted,
    and never cached by HTTP, so turning a setting off reaches the browsers on
    their next visit."""
    config = worker_config(request)
    body = render_to_string('gentelella/pwa/sw.js', {
        'config': json.dumps(config)})
    response = HttpResponse(body, content_type='application/javascript')
    response['Service-Worker-Allowed'] = config['scope']
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


@require_GET
def offline_view(request):
    """What the service worker shows for a page when there is no network."""
    return render(request, 'gentelella/pwa/offline.html', {
        'manifest': build_manifest(request)})


def _json_login_required(view):
    """403 json instead of the login redirect: the caller is a fetch()."""
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'detail': _('Authentication required.')},
                                status=403)
        return view(request, *args, **kwargs)
    wrapped.__name__ = view.__name__
    wrapped.__doc__ = view.__doc__
    return wrapped


def _json_body(request):
    try:
        return json.loads(request.body or b'{}')
    except (ValueError, UnicodeDecodeError):
        return None


@require_POST
@_json_login_required
def subscribe_view(request):
    """Store the ``PushSubscription.toJSON()`` the browser posts."""
    if not push.push_enabled():
        return JsonResponse({'detail': _('Push notifications are not available.')},
                            status=503)
    data = _json_body(request)
    try:
        subscription = push.subscribe(
            request.user, data, site=get_current_site(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''))
    except ValidationError as error:
        return JsonResponse({'detail': ' '.join(error.messages)}, status=400)
    return JsonResponse({'id': subscription.pk}, status=201)


@require_POST
@_json_login_required
def unsubscribe_view(request):
    """Forget the subscription whose ``endpoint`` is posted (only the user's)."""
    data = _json_body(request)
    endpoint = data.get('endpoint') if isinstance(data, dict) else None
    if not isinstance(endpoint, str) or not endpoint:
        return JsonResponse({'detail': _('Invalid subscription.')}, status=400)
    return JsonResponse({'deleted': push.unsubscribe(request.user, endpoint)})


@require_POST
@_json_login_required
def test_view(request):
    """Send a test push to every subscription of the user."""
    if not push.push_enabled():
        return JsonResponse({'detail': _('Push notifications are not available.')},
                            status=503)
    app = AppSettings(get_current_site(request))
    sent = push.send_push(request.user, {
        'title': app.name(),
        'body': _('Push notifications work on this device.'),
        'url': reverse('gt_push_preferences'),
        'tag': 'gt-push-test',
        'icon': app.icon('192'),
    }, respect_preference=False)
    return JsonResponse({'sent': sent})


@login_required
def preferences_view(request):
    """The user's push page: subscribe this browser, test it, and turn the
    push of the notifications on or off."""
    if request.method == 'POST':
        enabled = request.POST.get('enabled') in ('1', 'on', 'true')
        push.set_push_wanted(request.user, enabled)
        messages.success(request, _('Your push preference was saved.'))
        return redirect('gt_push_preferences')
    available = push.push_enabled()
    return render(request, 'gentelella/pwa/preferences.html', {
        'available': available,
        'application_server_key': (push.get_backend().application_server_key()
                                   if available else ''),
        'wanted': push.push_wanted(request.user),
        'subscriptions': PushSubscription.objects.filter(user=request.user),
        'scope': conf.scope(),
    })
