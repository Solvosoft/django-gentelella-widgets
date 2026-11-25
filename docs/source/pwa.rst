PWA and push notifications
==========================

``djgentelella.pwa`` lets a project be installed as an application (a
progressive web app) per Site, and sends the notifications of the bell
(:doc:`notifications`) to the browser as web push too, when the user accepts
it. Everything is off by default.

It is not a Django app: its models (``PushSubscription``, ``PushPreference``)
live in ``djgentelella/models.py`` and its URLs come with
``djgentelella.urls``.

Settings
--------

.. list-table::
   :header-rows: 1
   :widths: 32 15 53

   * - Setting
     - Default
     - Meaning
   * - ``GT_PWA_MANIFEST``
     - ``False``
     - The manifest tags in ``base.html`` (``<link rel="manifest">``,
       ``theme-color``, ``apple-touch-icon``).
   * - ``GT_PWA_SERVICE_WORKER``
     - ``False``
     - Every page registers the service worker: static cache and offline
       page.
   * - ``GT_PWA_SCOPE``
     - ``'/'``
     - Scope of the service worker and of the app.
   * - ``GT_PWA_CACHE_VERSION``
     - djgentelella's version
     - Names the static cache. Change it on each deploy that changes static
       files without changing their URLs.
   * - ``GT_PWA_CACHE_URLS``
     - ``[]``
     - URL prefixes cached besides ``STATIC_URL`` (opt-in: never a page or an
       API that depends on the user).
   * - ``GT_PWA_PRECACHE``
     - ``[]``
     - Static paths (or URLs) downloaded when the worker installs.
   * - ``GT_PWA_THEME_COLOR`` / ``GT_PWA_BACKGROUND_COLOR``
     - ``'#2A3F54'`` / ``'#F7F7F7'``
     - Colours when the Site has none.
   * - ``GT_PWA_DISPLAY``
     - ``'standalone'``
     - ``display`` of the manifest.
   * - ``GT_PUSH_BACKEND``
     - ``'djgentelella.pwa.backends.WebPushBackend'``
     - Class that sends a push (dotted path).
   * - ``GT_PUSH_VAPID_PRIVATE_KEY``
     - ``''``
     - VAPID private key: base64url (what ``gt_vapid_keys`` prints) or PEM
       text. Without it, push is off.
   * - ``GT_PUSH_VAPID_PUBLIC_KEY``
     - derived
     - The application server key the browser subscribes with.
   * - ``GT_PUSH_VAPID_SUBJECT``
     - ``'mailto:' + DEFAULT_FROM_EMAIL``
     - Contact the push services may use.
   * - ``GT_PUSH_TTL`` / ``GT_PUSH_TIMEOUT``
     - ``86400`` / ``5``
     - Seconds the push service keeps a message for an offline browser /
       seconds to wait for it.
   * - ``GT_PUSH_ALLOWED_HOSTS``
     - the browsers' push services
     - Hosts a subscription endpoint may point to (``.example.com`` covers
       its subdomains). ``None`` accepts any https host.
   * - ``GT_PUSH_QUEUE``
     - ``'sync'``
     - How a new notification goes out: ``'sync'`` after the commit in the
       same process, ``'celery'`` as the task
       ``djgentelella.pwa.tasks.push_notification_task``, ``'auto'`` through
       Celery when ``async_notification`` would (the ``celery`` extra and
       ``CELERY_BROKER_URL``).
   * - ``GT_PUSH_UNSUBSCRIBE_ON_LOGOUT``
     - ``False``
     - Logging out forgets the subscriptions that browser's session
       registered.

The manifest per Site
---------------------

``/pwa/manifest.webmanifest`` (``gt_pwa_manifest``) answers with the manifest
of the current Site (:doc:`sites`). Each value is a key of
``GentelellaSettings``: the Site's value wins over the global one, and
without either a default applies.

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Key
     - Manifest field
   * - ``pwa_name``
     - ``name``; else ``site_title``, else the Site's name.
   * - ``pwa_short_name``
     - ``short_name``; else the name cut to 12 characters.
   * - ``pwa_description``
     - ``description``.
   * - ``pwa_theme_color`` / ``pwa_background_color``
     - ``theme_color`` / ``background_color``.
   * - ``pwa_icon_192`` / ``pwa_icon_512``
     - The two icons (a static path, or a URL as it is); else djgentelella's.
   * - ``pwa_start_url``
     - ``start_url`` and ``id``; else the scope.
   * - ``pwa_scope``
     - ``scope`` (a path that starts and ends with ``/``: the prefix an
       application is served under); else ``GT_PWA_SCOPE``. The service worker
       of that Site is registered for it, and ``Service-Worker-Allowed``
       follows it.

.. code:: python

    from djgentelella.utils import set_settings

    set_settings('pwa_name', 'Inventory', site=inventory_site)
    set_settings('pwa_theme_color', '#0b7285', site=inventory_site)
    set_settings('pwa_icon_512', 'inventory/icon-512.png', site=inventory_site)

The tags go in the ``pwa_head`` block of ``gentelella/base.html``
(``{% load gtpwa %}{% pwa_head %}``); a template that overrides the block
can leave them out. All the keys are read in one query per page.

The service worker
------------------

``/pwa/sw.js`` (``gt_pwa_service_worker``) is served with
``Service-Worker-Allowed: <scope>`` and never cached by HTTP. With
``GT_PWA_SERVICE_WORKER`` on, ``gentelella/js/pwa/register.js`` registers it
on every page (``window.gt_pwa_registration`` is the promise).

What it does:

- **Static files** (``STATIC_URL`` and ``GT_PWA_CACHE_URLS``): cache first, in
  a cache named ``gt-pwa-<GT_PWA_CACHE_VERSION>``. A new version installs a
  new worker, which deletes the caches of the old one.
- **Pages** (navigations): always from the network, never stored, so an
  authenticated page stays on the server. Without network it shows the
  offline page (``/pwa/offline/``, ``gt_pwa_offline``, stored on install).
- **Anything else** (APIs, ``POST``, other origins): untouched, the browser
  does what it always does.

**Uninstalling.** Turn ``GT_PWA_SERVICE_WORKER`` off and the same URL serves a
worker that deletes its caches and unregisters itself; browsers pick it up
the next time they check ``sw.js`` (on a visit). With push on, the worker
stays, without the cache, because push needs it.

Web push
--------

Install the extra and generate a key pair once; keep the keys in the
environment, never in the repository::

    pip install djgentelella[push]
    python manage.py gt_vapid_keys

.. code:: python

    GT_PUSH_VAPID_PRIVATE_KEY = os.environ['GT_PUSH_VAPID_PRIVATE_KEY']
    GT_PUSH_VAPID_PUBLIC_KEY = os.environ['GT_PUSH_VAPID_PUBLIC_KEY']
    GT_PUSH_VAPID_SUBJECT = 'mailto:ops@example.com'

Then:

- Each user subscribes each browser at ``/pwa/push/``
  (``gt_push_preferences``): the page registers the service worker, asks for
  the permission and posts the subscription. The same page unsubscribes the
  device, sends a test push to every device of the user and turns the push of
  the notifications off or on (``PushPreference``; without a row it is on).
- Every new ``Notification`` (``create_notification()`` or
  ``Notification.objects.create()``; not ``bulk_create``, which sends no
  signal) is sent, after the transaction commits, to the subscriptions of its
  user. The payload is::

      {"title": "<name of the app of the subscription's Site>",
       "body": "<description>", "url": "<link>",
       "tag": "gt-notification-<id>", "type": "<message_type>", "id": <id>,
       "icon": "<pwa_icon_192>"}

  Clicking the notification focuses a tab on ``url`` or opens one.
- A subscription the push service no longer knows (``404``/``410``) is
  deleted; any other error is logged and the subscription is kept. The
  notification is created whatever happens to the push.
- Sending happens in the process that creates the notification, with
  ``GT_PUSH_TIMEOUT``, unless ``GT_PUSH_QUEUE`` queues it in Celery (the
  worker needs ``djgentelella.pwa.tasks`` among the modules it imports).

Endpoints (``POST``, JSON, CSRF token in ``X-CSRFToken``, ``403`` json without
a session):

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - URL (name)
     - Body / answer
   * - ``/pwa/push/subscribe/`` (``gt_push_subscribe``)
     - ``PushSubscription.toJSON()`` → ``201 {"id"}``; ``400`` for an endpoint
       that is not https or not a known push service, or bad keys; ``503``
       when push is off. An endpoint subscribed by another user moves to this
       one (one browser, one owner).
   * - ``/pwa/push/unsubscribe/`` (``gt_push_unsubscribe``)
     - ``{"endpoint"}`` → ``{"deleted": n}``, only among the user's.
   * - ``/pwa/push/test/`` (``gt_push_test``)
     - → ``{"sent": n}``.
   * - ``/pwa/push/resubscribe/`` (``gt_push_resubscribe``)
     - ``{"old": toJSON(), "new": toJSON()}`` → ``{"id"}``: the
       ``pushsubscriptionchange`` of the service worker. No session and no
       CSRF token: the ``auth`` secret of the old subscription, which only the
       browser and the server know, is the proof. ``404`` when the old one is
       not known, ``400`` for a bad body.

Sending something else::

    from djgentelella.pwa.push import send_push

    send_push(user, {'title': 'Stock', 'body': 'Item 12 is out of stock',
                     'url': '/inventory/12/'}, site=None)

``site`` limits it to that Site's subscriptions and the global ones;
``respect_preference=False`` ignores ``PushPreference``. ``payload`` can also
be a callable ``payload(site)`` to title each Site its own way.

Backends
--------

``djgentelella.pwa.backends``:

- ``WebPushBackend`` (default): ``pywebpush`` with the VAPID keys. Not
  ``available()`` without the extra or the private key.
- ``LocmemPushBackend``: keeps what it would send in
  ``LocmemPushBackend.outbox`` (no network); an endpoint in
  ``LocmemPushBackend.gone`` behaves as a ``410``. For tests and development.
- Your own: subclass ``BasePushBackend`` and implement ``send(subscription,
  payload)`` (``payload`` is the JSON text); raise ``PushGone`` for a
  subscription that no longer exists.

Notes
-----

- Service workers and push need a secure context: https, or ``localhost``
  while developing.
- Logging out does not unsubscribe the browser unless
  ``GT_PUSH_UNSUBSCRIBE_ON_LOGOUT``: then the subscriptions that session
  registered are forgotten (the browser keeps its own; the next visit to
  ``/pwa/push/`` after logging in registers it again). Otherwise the next
  user who subscribes it takes it over.
- ``pushsubscriptionchange`` (the browser renewing a subscription): the
  service worker sends the new subscription with the old one to
  ``/pwa/push/resubscribe/``, which replaces it in place.
- The demo turns the manifest on; ``DEMO_PWA_SERVICE_WORKER=1`` turns the
  worker on and ``DEMO_PUSH_LOCMEM=1`` (or real keys in
  ``GT_PUSH_VAPID_PRIVATE_KEY``/``GT_PUSH_VAPID_PUBLIC_KEY``) push.
