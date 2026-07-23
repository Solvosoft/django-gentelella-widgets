Base Templates &amp; Utilities
============================

A *base template* is an email-hardened HTML layout that wraps an email's body
(placed in ``{{ content }}``). Register the ones you want in
``ASYNC_NOTIFICATION_BASE_TEMPLATES`` and pick one per ``EmailTemplate`` /
``NewsLetter`` via its ``base_template`` field.

The module ships four layouts, each built for a purpose and hardened for real
mail clients (XHTML/Outlook doctype, MSO conditionals + VML buttons, a hidden
preheader, ``light dark`` color-scheme hints, and a 600px table layout with
inline styles plus a progressive-enhancement ``<style>`` block for responsive
and dark mode):

============== ============================================ ==================================
Key            Template                                     Use for
============== ============================================ ==================================
``executive``  ``async_notification/base/executive.html``   Official / corporate communications
``product``    ``async_notification/base/product.html``     Product launches & announcements
``transactional`` ``async_notification/base/transactional.html`` Receipts, codes, account alerts
``newsletter`` ``async_notification/base/newsletter.html``  Periodic multi-section digests
============== ============================================ ==================================

Registering them
----------------

.. code:: python

    ASYNC_NOTIFICATION_BASE_TEMPLATES = {
        "executive": "async_notification/base/executive.html",
        "product": "async_notification/base/product.html",
        "transactional": "async_notification/base/transactional.html",
        "newsletter": "async_notification/base/newsletter.html",
    }

Branding
--------

The base templates read ``{{ brand.* }}`` from ``ASYNC_NOTIFICATION_BRAND``,
injected automatically on both the send and preview paths. Every key is
optional; templates degrade gracefully when a value is missing.

.. code:: python

    ASYNC_NOTIFICATION_BRAND = {
        "name": "Acme Inc",
        "logo_url": "https://cdn.acme.com/logo.png",  # absolute URL
        "color": "#3b5bdb",                            # primary/accent hex
        "color_text_on": "#ffffff",                    # text on the accent
        "site_url": "https://acme.com",
        "address": "Acme Inc, 123 Main St",
        "support_email": "support@acme.com",
        "tagline": "Building better software",
    }

The ``product`` layout also renders a call-to-action button when ``cta_url``
(and optional ``cta_label``) is supplied in the template context.

Utility partials
----------------

Reusable components live under ``async_notification/base/utils/`` and are meant
to be ``{% include %}``-d inside an ``EmailTemplate`` body (which is rendered by
the Django template engine) or in the live preview:

.. code:: html

    {% include "async_notification/base/utils/button.html" with url="https://acme.com/go" label="Get started" %}
    {% include "async_notification/base/utils/info_box.html" with title="Heads up" text="Your trial ends soon." %}
    {% include "async_notification/base/utils/divider.html" %}
    {% include "async_notification/base/utils/spacer.html" with height=24 %}

- ``button.html`` — bulletproof CTA (renders in Outlook via VML). Params:
  ``url``, ``label``, ``color``, ``text_color``.
- ``info_box.html`` — accent callout. Params: ``title``, ``text``, ``color``, ``bg``.
- ``divider.html`` — horizontal rule. Params: ``color``, ``space``.
- ``spacer.html`` — vertical spacing. Param: ``height``.
