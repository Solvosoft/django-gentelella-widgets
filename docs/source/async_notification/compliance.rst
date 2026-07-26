Deliverability & Compliance
===========================

The module ships the pieces a real sender needs to stay out of spam folders and
honor opt-outs: a promotional/transactional distinction, a suppression list,
optional opt-in enforcement, one-click unsubscribe (RFC 8058), a physical
mailing-address footer (CAN-SPAM), and a bounce/complaint webhook.

Promotional vs. transactional
-----------------------------

Every :class:`EmailNotification` has an ``is_promotional`` flag (newsletters are
always promotional):

- **Transactional** (``is_promotional=False``, the default) — password resets,
  receipts, alerts. Sent as batched messages. The suppression list is **ignored**
  so these always reach the user.
- **Promotional** (``is_promotional=True``) — marketing / newsletters. Sent one
  message per recipient, each carrying its own one-click unsubscribe header and a
  visible footer. Suppressed (and, when opt-in is required, non-consented)
  addresses are dropped before sending.

Suppression list
----------------

``EmailSuppression`` holds addresses that must not receive promotional email.
It is populated by one-click unsubscribes, the webhook, or manually. Addresses
are stored and matched **case-insensitively** (normalized to lower case), so an
unsubscribe as ``User@Example.com`` still suppresses a later ``user@example.com``
send.

.. code:: python

    from djgentelella.async_notification.models import EmailSuppression

    EmailSuppression.objects.create(email='user@example.com', reason='complaint')
    # reason ∈ {'unsubscribe', 'complaint', 'bounce', 'manual'}

Opt-in (double opt-in)
----------------------

When ``ASYNC_NOTIFICATION_REQUIRE_OPTIN = True``, promotional mail only reaches
addresses with a granted ``EmailConsent`` record (also matched
case-insensitively):

.. code:: python

    from djgentelella.async_notification.models import EmailConsent

    EmailConsent.objects.create(email='user@example.com', granted=True,
                                source='signup-form')

One-click unsubscribe (RFC 8058)
--------------------------------

Promotional messages include ``List-Unsubscribe`` and
``List-Unsubscribe-Post: List-Unsubscribe=One-Click`` headers built from a
signed, per-recipient token (``django.core.signing``, HMAC — unguessable and
tamper-proof). A mailbox provider POSTs the token URL; the address is added to
the suppression list. A person clicking the footer link gets a confirmation page
whose button POSTs the same URL. ``GET`` is side-effect-free (safe for scanners
and link prefetch); only ``POST`` suppresses.

Set ``ASYNC_NOTIFICATION_BASE_URL`` to an **HTTPS** origin so the one-click URL
can be built (Gmail/Yahoo ignore an ``http://`` one-click target); the Sites
framework is used as a fallback. ``ASYNC_NOTIFICATION_UNSUBSCRIBE_MAILTO``
adds a ``mailto:`` fallback, and ``ASYNC_NOTIFICATION_MAILING_ADDRESS`` fills the
CAN-SPAM footer.

Suppression webhook
-------------------

``async_notification:suppression_webhook`` lets a mail provider report bounces
and complaints. It is **disabled (404)** unless
``ASYNC_NOTIFICATION_WEBHOOK_SECRET`` is set. The secret must be sent in the
``X-Webhook-Secret`` header (never the query string, which leaks into logs) and
is compared in constant time.

.. code:: bash

    curl -X POST https://app.example.com/async_notification/webhook/suppression/ \
         -H "X-Webhook-Secret: $SECRET" \
         -H "Content-Type: application/json" \
         -d '{"email": "bounced@example.com", "reason": "bounce"}'

Compliance settings
-------------------

.. code:: python

    # HTTPS origin used to build the one-click unsubscribe link.
    ASYNC_NOTIFICATION_BASE_URL = 'https://app.example.com'

    # mailto: fallback for List-Unsubscribe (None disables it).
    ASYNC_NOTIFICATION_UNSUBSCRIBE_MAILTO = 'unsubscribe@example.com'

    # Physical mailing address shown in the promotional footer (CAN-SPAM).
    ASYNC_NOTIFICATION_MAILING_ADDRESS = 'Acme Inc, 123 Main St, City'

    # List-Id header value for newsletters.
    ASYNC_NOTIFICATION_LIST_ID = 'News <news.example.com>'

    # Max age (seconds) for unsubscribe tokens; None = never expire.
    ASYNC_NOTIFICATION_UNSUBSCRIBE_MAX_AGE = None

    # Throttle: max messages per minute (0 = no limit).
    ASYNC_NOTIFICATION_RATE_LIMIT = 0

    # Require a granted EmailConsent before sending promotional email.
    ASYNC_NOTIFICATION_REQUIRE_OPTIN = False

    # Shared secret for the suppression webhook (None disables the endpoint).
    ASYNC_NOTIFICATION_WEBHOOK_SECRET = None
