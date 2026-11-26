from django.conf import settings
from django.utils.module_loading import import_string

from djgentelella.sites import get_current_site
from djgentelella.utils import get_settings

#: The values of the ``feedback_enabled`` setting that turn it off.
OFF = ('false', '0', 'no', 'off')


def feedback_enabled(request):
    """Whether ``request`` gets the feedback button: ``GT_FEEDBACK`` is on,
    the Site did not turn it off (``feedback_enabled``, its own value or the
    global one) and the user is logged in."""
    if not getattr(settings, 'GT_FEEDBACK', False) or request is None:
        return False
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return False
    value = get_settings('feedback_enabled', site=get_current_site(request))
    return str(value).strip().lower() not in OFF


#: The permissions that make a reviewer (``view``) and let them answer
#: (``change``) when ``GT_FEEDBACK_REVIEWER`` is not set.
REVIEW_PERMISSION = 'djgentelella.view_feedback'
ANSWER_PERMISSION = 'djgentelella.change_feedback'


def _hook(name):
    value = getattr(settings, name, None)
    if isinstance(value, str) and value:
        return import_string(value)
    return value if callable(value) else None


def is_feedback_reviewer(request, user=None):
    """Whether ``user`` (the request's by default) reviews the feedback of
    the request's Site: sees the inbox and the feedback of that Site.

    ``GT_FEEDBACK_REVIEWER`` -- a callable or its dotted path,
    ``(request, user) -> bool`` -- decides when it is set (the reviewers of
    each Site, a group per application...); otherwise the global permission
    ``djgentelella.view_feedback``. An anonymous user never is one.
    """
    user = user if user is not None else getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return False
    hook = _hook('GT_FEEDBACK_REVIEWER')
    if hook is not None:
        return bool(hook(request, user))
    return user.has_perm(REVIEW_PERMISSION)


def can_answer_feedback(request, user=None):
    """Whether ``user`` answers (and changes the status of) the feedback of
    the request's Site.

    ``GT_FEEDBACK_ANSWERER`` (``(request, user) -> bool``) when set; else,
    with ``GT_FEEDBACK_REVIEWER`` set, every reviewer it accepts answers too;
    else the global permission ``djgentelella.change_feedback``.
    """
    user = user if user is not None else getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return False
    hook = _hook('GT_FEEDBACK_ANSWERER')
    if hook is not None:
        return bool(hook(request, user))
    if _hook('GT_FEEDBACK_REVIEWER') is not None:
        return is_feedback_reviewer(request, user)
    return user.has_perm(ANSWER_PERMISSION)
