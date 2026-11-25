from django.conf import settings

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
