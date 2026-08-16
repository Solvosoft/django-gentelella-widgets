from django.apps import AppConfig
from django.utils.module_loading import import_string


class AsyncNotificationConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'djgentelella.async_notification'
    verbose_name = 'Async Notification'

    def ready(self):
        # Deferred on purpose: ready() runs while the app registry is being
        # populated, so these modules (which touch models) cannot be imported
        # at module level.
        from djgentelella.async_notification.resolvers import (  # noqa: PLC0415
            RecipientResolverRegistry, DjangoGroupResolver,
            ContentTypeResolver,
        )
        from djgentelella.async_notification.interfaces import (  # noqa: PLC0415
            register_news_basemodel
        )
        from djgentelella.async_notification.settings import (  # noqa: PLC0415
            ASYNC_NOTIFICATION_RESOLVERS, ASYNC_NEWS_BASE_MODELS
        )

        # Default resolvers plus any registered from settings.
        RecipientResolverRegistry.register('group.local', DjangoGroupResolver)
        # ContentType resolver for <pk>@<app_label>.<model_name>.internal
        RecipientResolverRegistry.register('internal', ContentTypeResolver)
        for suffix, path in ASYNC_NOTIFICATION_RESOLVERS.items():
            try:
                RecipientResolverRegistry.register(
                    suffix, import_string(path))
            except ImportError:
                pass

        # Seed newsletter base-model interfaces from settings.
        # Entry shape: [dotted_model, description, interface_path].
        for key, entry in ASYNC_NEWS_BASE_MODELS.items():
            if isinstance(entry, (list, tuple)) and len(entry) >= 3:
                try:
                    register_news_basemodel(key, entry[1], entry[2])
                except ImportError:
                    pass

        # Import signals to connect them
        import djgentelella.async_notification.signals  # noqa: F401,PLC0415
