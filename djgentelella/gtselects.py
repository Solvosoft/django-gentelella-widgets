from django.contrib.auth.models import User, Group

from djgentelella.groute import register_lookups
from djgentelella.objectmanagement import AuthAllPermBaseObjectManagement
from djgentelella.views.select2autocomplete import BaseSelect2View


@register_lookups(prefix="userbase", basename="userbase")
class User(AuthAllPermBaseObjectManagement, BaseSelect2View):
    model = User
    fields = ['username']
    perms = {
        'list': ['auth.change_user'],
    }


@register_lookups(prefix="groupbase", basename="groupbase")
class Group(AuthAllPermBaseObjectManagement, BaseSelect2View):
    model = Group
    fields = ['name']
    perms = {
        'list': ['auth.change_group'],
    }
