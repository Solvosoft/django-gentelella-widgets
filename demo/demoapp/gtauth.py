"""Authorizations of the demo (see docs/source/authorization.rst).

Usable from any condition, e.g. ``MenuItem.condition = {"auth": "demo.staff"}``.
"""

from djgentelella.authorization import authorization


@authorization('demo.staff')
def staff(request, obj=None):
    return request.user.is_staff


@authorization('demo.country_editor')
def country_editor(request, obj=None):
    """Who may change countries."""
    return request.user.has_perm('demoapp.change_country')
