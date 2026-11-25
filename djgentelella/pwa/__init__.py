"""Progressive web app and web push for djgentelella.

- A web app manifest per Site (``/pwa/manifest.webmanifest``) and its tags in
  ``base.html`` behind ``GT_PWA_MANIFEST``.
- A service worker (``/pwa/sw.js``) registered behind
  ``GT_PWA_SERVICE_WORKER``: a versioned cache of the static files and an
  offline page; pages and APIs are not cached.
- Web push (VAPID) of the notifications, with ``pywebpush`` (the ``[push]``
  extra) behind a pluggable backend (``GT_PUSH_BACKEND``).

Not a Django app: its models live in ``djgentelella/models.py``. See
``docs/source/pwa.rst``.
"""
