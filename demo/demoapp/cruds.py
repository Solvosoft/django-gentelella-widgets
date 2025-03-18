from demoapp.models import Person, Country
from djgentelella.cruds.base import CRUDView
from djgentelella.models import MenuItem


class Personclass(CRUDView):
    model = Person
    check_login = False
    check_perms = False


class Countryclass(CRUDView):
    model = Country
    check_login = False
    check_perms = False


class MenuItemclass(CRUDView):
    model = MenuItem
    check_login = False
    check_perms = False
    search_fields = ['title']
