
from rest_framework.routers import SimpleRouter

routes = SimpleRouter()

def register_lookups(prefix='', basename=None):
    """
    See https://www.django-rest-framework.org/api-guide/routers/#usage
    :param prefix:
    :param basename:
    :return:
    """
    def wrap(func):
        return func
    @wrap
    def decore(klass):
        routes.register(prefix, klass, basename=basename)

    return decore

