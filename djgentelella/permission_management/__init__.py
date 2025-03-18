from django.core.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission


def any_permission(user, perms, raise_exception=False):
    for perm in perms:
        # First check if the user has the permission (even anon users)
        if user.has_perm(perm):
            return True
    if raise_exception:
        raise PermissionDenied
    return False


def all_permission(user, perms, raise_exception=False):
    # First check if the user has the permission (even anon users)
    if perms and user.has_perms(perms):
        return True
    # In case the 403 handler should be called raise the exception
    if raise_exception:
        raise PermissionDenied
    # As the last resort, show the login form
    return False


class AllPermission(BasePermission):
    def __init__(self, perms):
        self.perms = perms
        super().__init__()

    def has_permission(self, request, view):
        return all_permission(request.user, self.perms)


class AnyPermission(BasePermission):
    def __init__(self, perms):
        self.perms = perms
        super().__init__()

    def has_permission(self, request, view):
        return any_permission(request.user, self.perms)


class AllPermissionByAction(BasePermission):
    def has_permission(self, request, view):
        perms = view.perms[view.action]
        return all_permission(request.user, perms)


class AnyPermissionByAction(BasePermission):
    def has_permission(self, request, view):
        perms = view.perms[view.action]
        return any_permission(request.user, perms)
