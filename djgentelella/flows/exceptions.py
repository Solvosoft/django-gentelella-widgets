"""What the engine and the tasks refuse with. Both are ``PermissionDenied``:
a view that lets one escape answers 403."""

from django.core.exceptions import PermissionDenied


class TransitionNotAllowed(PermissionDenied):
    """The transition cannot run on this object, for this user, now."""


class TransitionBlocked(TransitionNotAllowed):
    """Raised by a ``condition`` to say why: the text is shown to the user,
    on the disabled button and when the transition is refused."""


class TaskNotAllowed(PermissionDenied):
    """The user cannot do that to the task, or not in its current state."""


class ActionNotAllowed(TransitionNotAllowed):
    """The action policy (``GT_FLOWS_ACTION_POLICY``, or the context's own)
    refused to run an action. Raised before the action runs: the transition
    is refused, an activity is left in error."""
