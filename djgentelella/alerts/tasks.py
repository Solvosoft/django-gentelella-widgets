"""Celery task of the alerts, when Celery is installed.

Celery's autodiscovery does not reach this module (djgentelella.alerts is
not an app): list it, ``app.autodiscover_tasks(['djgentelella.alerts'])``, and
schedule it per process in beat::

    'equipment-due': {
        'task': 'djgentelella.alerts.tasks.run_alert_rules_task',
        'schedule': crontab(hour=7, minute=10),
        'args': ('lab.equipment_due',),
    }

Without Celery, call ``run_alert_rules(code)`` from a cron job.
"""

from .engine import run_alert_rules

try:
    from celery import shared_task

    @shared_task
    def run_alert_rules_task(process_code, **kwargs):
        return run_alert_rules(process_code, **kwargs)

except ImportError:
    pass
