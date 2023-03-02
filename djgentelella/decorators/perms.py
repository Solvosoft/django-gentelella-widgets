from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied


def any_permission_required(perms, login_url=None, raise_exception=False):
    """
    Decorator for views that checks whether user has any permission
    enabled in perms list, redirecting to the log-in page if necessary.
    If the raise_exception parameter is given the PermissionDenied exception
    is raised.
    """

    def check_perms(user):

        for perm in perms:
            # First check if the user has the permission (even anon users)
            if user.has_perm(perm):
                return True
        # In case the 403 handler should be called raise the exception
        if raise_exception:
            raise PermissionDenied
        # As the last resort, show the login form
        return False

    return user_passes_test(check_perms, login_url=login_url)


def all_permission_required(perms, login_url=None, raise_exception=False):
    """
    Decorator for views that checks whether user has all permission
    enabled in perms list, redirecting to the log-in page if necessary.
    If the raise_exception parameter is given the PermissionDenied exception
    is raised.
    """

    def check_perms(user):
        # First check if the user has the permission (even anon users)
        if user.has_perms(perms):
            return True
        # In case the 403 handler should be called raise the exception
        if raise_exception:
            raise PermissionDenied
        # As the last resort, show the login form
        return False

    return user_passes_test(check_perms, login_url=login_url)
