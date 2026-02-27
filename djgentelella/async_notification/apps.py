from django.apps import AppConfig


class AsyncNotificationConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'djgentelella.async_notification'
    verbose_name = 'Async Notification'

    def ready(self):
        from djgentelella.async_notification.resolvers import (
            RecipientResolverRegistry, DjangoGroupResolver
        )
        RecipientResolverRegistry.register('group.local', DjangoGroupResolver)
        # Import signals to connect them
        import djgentelella.async_notification.signals  # noqa: F401
