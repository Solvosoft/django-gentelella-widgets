from django.contrib.auth.models import User, Group

from djgentelella.groute import register_lookups
from djgentelella.permission_management import AllPermission
from djgentelella.views.select2autocomplete import BaseSelect2View


@register_lookups(prefix="userbase", basename="userbase")
class User(BaseSelect2View, AllPermission):
    model = User
    fields = ['username']
    perms = ['auth.change_user']


@register_lookups(prefix="groupbase", basename="groupbase")
class Group(BaseSelect2View, AllPermission):
    model = Group
    fields = ['name']
    perms = ['auth.change_group']
