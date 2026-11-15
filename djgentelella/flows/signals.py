"""The flow engine's signals. All of them are sent inside the transaction of
the change they announce: a receiver that raises undoes it.

``pre_transition`` / ``post_transition``: ``sender`` is the flow class; the
arguments are ``flow``, ``obj``, ``instance``, ``transition``, ``user``
(``None`` for the system), ``source``, ``target`` and ``kind``
(``'transition'``, ``'auto'`` or ``'timeout'``).

``flow_state_changed``: ``sender`` is the flow class; ``flow``, ``instance``,
``old`` and ``new`` (the values of ``FlowInstance.state``).

``task_created`` / ``task_completed``: ``sender`` is ``Task``; ``task`` and
``user``, plus ``outcome`` when completed. The engine itself listens to
``task_completed`` to move the flow the task belongs to.

``action_blocked``: ``sender`` is the action class; ``action``, ``context``
and ``reason``. Sent when the action policy refuses an action, right before
:class:`~djgentelella.flows.exceptions.ActionNotAllowed` is raised -- what a
receiver writes in the database goes away with the transaction that is
undone, so audit trails that must survive it log or write elsewhere.
"""

from django.dispatch import Signal

#: Before the actions of a transition run.
pre_transition = Signal()
#: After the state changed and the log row was written.
post_transition = Signal()
#: Whenever ``FlowInstance.state`` changes, by a transition or an activity.
flow_state_changed = Signal()
task_created = Signal()
task_completed = Signal()
#: The action policy refused to run an action.
action_blocked = Signal()
