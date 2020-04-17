from demoapp.models import Person
from djgentelella.cruds.base import CRUDView


class Personclass(CRUDView):
    model = Person
    check_login = False
    check_perms = False
