"""The task inbox as a data source (``flows.tasks``).

``djgentelella.datasources`` imports this module from its ``ready()`` when both
apps are installed; without ``djgentelella.datasources`` nothing imports it.
The rows are the tasks the inbox shows (``visible_tasks``): those of the user
and of their groups, every task with ``gtflows.view_task``. So the facets
(state, priority, flow, due date) and the exports of the data sources work on
the inbox.
"""
from django.utils.translation import gettext_lazy as _

from djgentelella.datasources.base import ModelDataSource, register_datasource
from djgentelella.flows.models import Task
from djgentelella.flows.views import visible_tasks


@register_datasource
class TaskDataSource(ModelDataSource):
    model = Task
    name = 'flows.tasks'
    label = _('Tasks')
    fields = ['id', 'title', 'state', 'priority', 'due', 'instance__flow',
              'actual_owner', 'outcome', 'created_at', 'completed_at']
    #: Anyone signed in: every user has an inbox, maybe empty.
    perms = []

    def has_permission(self, request):
        user = getattr(request, 'user', None)
        return user is not None and user.is_authenticated

    def base_queryset(self, request):
        # for_user() is distinct(): filtering by its pks keeps the grouping
        # and the counts of the facets free of it.
        visible = visible_tasks(request.user)
        return Task.objects.filter(pk__in=visible.values('pk'))
