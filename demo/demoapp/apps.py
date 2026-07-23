import logging
import os
import threading
import time

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class DemoappConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'demoapp'

    def ready(self):
        self._start_notification_poller()
        # Register an email-template context so the model inspector and
        # dummy-data preview work in the async_notification demo.
        from djgentelella.async_notification.registry import register_context
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

    def _start_notification_poller(self):
        """Dev-only stand-in for a cron: nothing else ever calls
        ``process_notifications`` on its own, so a due NewsLetterTask (or a
        queued EmailNotification) just sits there until someone runs it by
        hand. `runserver` has no cron either, so simulate one with a
        background thread purely for local testing convenience — a real
        deployment should wire an actual cron/scheduler instead.
        """
        # Skip: not the actual serving process (runserver's reloader spawns
        # a watcher parent with RUN_MAIN unset, then a child with it set to
        # 'true' that's the one handling requests) or any other management
        # command (test, migrate, shell...), where a background poller
        # would be pure noise/risk.
        if os.environ.get('RUN_MAIN') != 'true':
            return

        interval = int(os.getenv('ASYNC_NOTIFICATION_POLL_INTERVAL', '15'))

        def _loop():
            from django.core.management import call_command
            while True:
                try:
                    call_command('process_notifications')
                except Exception:
                    logger.exception('async_notification poller failed')
                time.sleep(interval)

        threading.Thread(
            target=_loop, daemon=True, name='async-notification-poller',
        ).start()
        logger.info(
            'async_notification: polling process_notifications every %ss.',
            interval)
