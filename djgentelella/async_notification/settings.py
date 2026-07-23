from django.conf import settings

# Backend for sending notifications.
# None = autodetect (Celery if available, otherwise sync)
ASYNC_NOTIFICATION_BACKEND = getattr(
    settings, 'ASYNC_NOTIFICATION_BACKEND', None)

# Maximum number of recipients per email batch
ASYNC_NOTIFICATION_MAX_PER_MAIL = getattr(
    settings, 'ASYNC_NOTIFICATION_MAX_PER_MAIL', 40)

# Maximum number of retry attempts for failed sends
ASYNC_NOTIFICATION_MAX_RETRIES = getattr(
    settings, 'ASYNC_NOTIFICATION_MAX_RETRIES', 3)

# Base delay (seconds) between retries; grows exponentially per attempt
ASYNC_NOTIFICATION_RETRY_DELAY = getattr(
    settings, 'ASYNC_NOTIFICATION_RETRY_DELAY', 60)

# Custom recipient resolvers registered by suffix:
# {'suffix': 'dotted.path.ResolverClass', ...}
ASYNC_NOTIFICATION_RESOLVERS = getattr(
    settings, 'ASYNC_NOTIFICATION_RESOLVERS', {})

# Default BCC addresses (comma-separated string or None)
ASYNC_BCC = getattr(settings, 'ASYNC_BCC', None)

# Default CC addresses (comma-separated string or None)
ASYNC_CC = getattr(settings, 'ASYNC_CC', None)

# If set, only send email (skip DB notification creation)
ASYNC_SEND_ONLY_EMAIL = getattr(settings, 'ASYNC_SEND_ONLY_EMAIL', None)

# Enable SMTP debug output
ASYNC_SMTP_DEBUG = getattr(settings, 'ASYNC_SMTP_DEBUG', False)

# Base templates for email wrapping: {'key': 'template/path.html', ...}
ASYNC_NOTIFICATION_BASE_TEMPLATES = getattr(
    settings, 'ASYNC_NOTIFICATION_BASE_TEMPLATES', {})

# Custom SMTP server configs for newsletters:
# {'config_name': {'host': ..., 'port': ..., 'username': ..., 'password': ..., 'use_tls': ...}}
ASYNC_NEWSLETTER_SEVER_CONFIGS = getattr(
    settings, 'ASYNC_NEWSLETTER_SEVER_CONFIGS', None)

# Model bases for newsletter templates: {'key': 'app_label.ModelName', ...}
ASYNC_NEWS_BASE_MODELS = getattr(
    settings, 'ASYNC_NEWS_BASE_MODELS', {})

# Newsletter header configuration: {'logo': ..., 'title': ..., ...}
ASYNC_NEWSLETTER_HEADER = getattr(
    settings, 'ASYNC_NEWSLETTER_HEADER', {})

# User lookup fields for autocomplete
ASYNC_NOTIFICATION_USER_LOOKUP_FIELDS = getattr(
    settings, 'ASYNC_NOTIFICATION_USER_LOOKUP_FIELDS',
    ['username', 'email', 'first_name', 'last_name'])

# Group lookup fields for autocomplete
ASYNC_NOTIFICATION_GROUP_LOOKUP_FIELDS = getattr(
    settings, 'ASYNC_NOTIFICATION_GROUP_LOOKUP_FIELDS',
    ['name'])

# Permission classes for API views (list of dotted paths)
ASYNC_NOTIFICATION_PERMISSION_CLASSES = getattr(
    settings, 'ASYNC_NOTIFICATION_PERMISSION_CLASSES', None)

# --- Compliance / deliverability (promotional email & newsletters) ---

# Absolute base URL (e.g. 'https://app.example.com') used to build the HTTPS
# one-click unsubscribe link in the List-Unsubscribe header. If empty, falls
# back to the Sites framework; without either, only the mailto: form is used.
ASYNC_NOTIFICATION_BASE_URL = getattr(
    settings, 'ASYNC_NOTIFICATION_BASE_URL', '')

# mailto: fallback address for the List-Unsubscribe header (None disables it).
ASYNC_NOTIFICATION_UNSUBSCRIBE_MAILTO = getattr(
    settings, 'ASYNC_NOTIFICATION_UNSUBSCRIBE_MAILTO', None)

# Physical mailing address shown in the promotional footer (CAN-SPAM).
ASYNC_NOTIFICATION_MAILING_ADDRESS = getattr(
    settings, 'ASYNC_NOTIFICATION_MAILING_ADDRESS', '')

# Value for the List-Id header on newsletters (e.g. 'News <news.example.com>').
ASYNC_NOTIFICATION_LIST_ID = getattr(
    settings, 'ASYNC_NOTIFICATION_LIST_ID', None)

# Max age (seconds) for unsubscribe tokens; None = never expire.
ASYNC_NOTIFICATION_UNSUBSCRIBE_MAX_AGE = getattr(
    settings, 'ASYNC_NOTIFICATION_UNSUBSCRIBE_MAX_AGE', None)

# Throttle: max messages per minute (0 = no limit).
ASYNC_NOTIFICATION_RATE_LIMIT = getattr(
    settings, 'ASYNC_NOTIFICATION_RATE_LIMIT', 0)

# Require an opt-in EmailConsent record before sending promotional email.
ASYNC_NOTIFICATION_REQUIRE_OPTIN = getattr(
    settings, 'ASYNC_NOTIFICATION_REQUIRE_OPTIN', False)

# Shared secret required by the suppression webhook (None disables the hook).
ASYNC_NOTIFICATION_WEBHOOK_SECRET = getattr(
    settings, 'ASYNC_NOTIFICATION_WEBHOOK_SECRET', None)

# --- Compose helpers (uploads) & worker recovery ---

# Max size (bytes) accepted by the image/video upload endpoints.
ASYNC_NOTIFICATION_UPLOAD_MAX_SIZE = getattr(
    settings, 'ASYNC_NOTIFICATION_UPLOAD_MAX_SIZE', 10 * 1024 * 1024)

# Content types accepted by the inline-image upload endpoint.
ASYNC_NOTIFICATION_IMAGE_CONTENT_TYPES = getattr(
    settings, 'ASYNC_NOTIFICATION_IMAGE_CONTENT_TYPES',
    ['image/png', 'image/jpeg', 'image/gif', 'image/webp'])

# Content types accepted by the video upload endpoint.
ASYNC_NOTIFICATION_VIDEO_CONTENT_TYPES = getattr(
    settings, 'ASYNC_NOTIFICATION_VIDEO_CONTENT_TYPES',
    ['video/mp4', 'video/webm', 'video/ogg'])

# A notification/task left in 'sending' for longer than this many minutes is
# assumed to belong to a dead worker and is reset to 'pending' by the cron
# command so it can be retried instead of stalling forever.
ASYNC_NOTIFICATION_STUCK_MINUTES = getattr(
    settings, 'ASYNC_NOTIFICATION_STUCK_MINUTES', 30)
