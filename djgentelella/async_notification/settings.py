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
