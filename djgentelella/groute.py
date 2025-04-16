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
        if basename in ['userbase', 'groupbase']:
            from djgentelella import settings
            if klass.__module__ == 'djgentelella.gtselects':
                if settings.REGISTER_DEFAULT_USER_API:
                    routes.register(prefix, klass, basename=basename)
            else:
                routes.register(prefix, klass, basename=basename)
        else:
            routes.register(prefix, klass, basename=basename)

    return decore
