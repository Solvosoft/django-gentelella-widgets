"""Run the flow timers past due -- deadlines, waits and task deadlines.
Designed for cron; with Celery, schedule
``djgentelella.flows.tasks.process_flow_timers_task`` in beat instead. Both
call :func:`djgentelella.flows.timers.process_due`."""

from django.core.management.base import BaseCommand

from djgentelella.flows.timers import due_instances, due_tasks, process_due


class Command(BaseCommand):
    help = 'Run the deadlines, waits and task deadlines of the flows past due.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='List what is due, change nothing.')

    def handle(self, *args, **options):
        if options['dry_run']:
            due = due_instances()
            for flow, pk in due:
                self.stdout.write('%s: instance %s' % (flow.name, pk))
            tasks = list(due_tasks())
            for task in tasks:
                self.stdout.write('task %s: %s' % (task.pk, task))
            self.stdout.write('%d due' % (len(due) + len(tasks)))
            return
        counts = process_due()
        self.stdout.write(', '.join('%s: %d' % item for item in sorted(
            counts.items(), key=lambda item: str(item[0]))) or 'Nothing due')
