from django.apps import AppConfig


class DemoappConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'demoapp'

    def ready(self):
        # Register an email-template context so the model inspector and
        # dummy-data preview work in the async_notification demo.
        # ready() runs while the app registry is loading: importing the
        # registry (and through it the models) at module level is not allowed.
        from djgentelella.async_notification.registry import (  # noqa: PLC0415
            register_context,
        )
        register_context(
            code='welcome',
            subject='Welcome {{ user.first_name }}',
            models={'user': 'auth.User'},
            exclude={'user': ['password', 'last_login']},
            extra_variables={
                'site_url': 'URL of the site',
                'year': 'Current year',
            },
        )
        register_context(
            code='order_summary',
            subject='Resumen de pedido para {{ customer.name }}',
            models={
                'customer': 'demoapp.Customer',
                'employee': 'demoapp.Employee',
                'person': 'demoapp.Person',
            },
            exclude={
                'customer': ['is_deleted'],
            },
            extra_variables={
                'site_url': 'URL of the site',
                'year': 'Current year',
            },
        )
