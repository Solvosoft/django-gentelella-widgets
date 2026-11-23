========================================================
Authorization: named rules, conditions and feature flags
========================================================

``djgentelella.authorization`` gives a project three things, in the spirit of
the "authorization schemes", conditions and "build options" of Oracle APEX:

* **authorizations**: access rules written as Python functions, with a name,
  so they can be reused from views, templates, menus, designs and flows;
* **conditions**: a small JSON format that combines permissions, groups,
  authorizations, settings and flags, to show or hide a menu item, a design
  node, a column, a button or a flow branch;
* **feature flags**: settings that turn a part of the application on or off,
  globally or for one Site.

It is a plain module of ``djgentelella``: there is nothing to add to
``INSTALLED_APPS`` and no migration of its own (``MenuItem.condition`` comes
with ``djgentelella``'s ``0023_menuitem_condition``). It can be imported
before the app registry is ready -- from a settings module or the
``AppConfig`` module of another app -- because it loads no model when it is
imported; ``ConditionRequiredMixin`` lives in
``djgentelella.views.conditions`` and is imported from there the first time
it is asked for.

The messages of ``validate_condition`` are translated, in the language
active when it runs.


Authorizations
==============

An authorization is ``function(request, obj=None) -> bool``, registered with a
name in ``<app>/gtauth.py``. Every installed app's ``gtauth.py`` is imported
when Django starts (``AppConfig.ready()``), so Celery workers and management
commands see them too.

.. code:: python

    # ventas/gtauth.py
    from djgentelella.authorization import authorization


    @authorization('es_supervisor')
    def es_supervisor(request, obj=None):
        return request.user.groups.filter(name='Supervisores').exists()


    @authorization('es_dueno')
    def es_dueno(request, obj=None):
        # Evaluated without an object for the view (see ConditionPermission)
        # and with it for each object.
        return obj is None or obj.vendedor_id == request.user.pk


    @authorization('cupo_disponible', cache=False)
    def cupo_disponible(request, obj=None):
        return Cupo.objects.filter(abierto=True).exists()

.. code:: python

    from djgentelella.authorization import check_authorization

    if check_authorization('es_supervisor', request):
        ...

* The result is **cached on the request**, per user and object (a saved model
  instance; other objects are not cached), so a page that asks the same thing
  ten times runs the function once. ``cache=False`` runs it every time.
* An **unknown name** is ``False`` and is logged (``djgentelella.authorization``
  logger, ``ERROR``); so is a function that raises. A broken rule closes, it
  does not open. When saving a condition (the menu admin, publishing a design
  or a flow), an unknown name is a validation error instead.
* Registering the same name again replaces the function.
* ``get_authorizations()`` returns ``{name: function}``, for an editor that
  offers the names.


Conditions
==========

A condition is a JSON object with exactly one of these keys:

===============================================  ===========================================
node                                              holds when
===============================================  ===========================================
``{"perm": "app.codename"}``                      the user has the permission; a list needs
                                                  all of them. With an object, object
                                                  permissions (django-guardian) count too
``{"auth": "name"}``                              the authorization holds (with the object)
``{"group": "Finanzas"}``                         the user is in the group, in the current
                                                  Site (see `Roles by Site`_); a list needs
                                                  any of them
``{"setting": "key", "equals": "v"}``             the setting, with the Site rule of
                                                  :doc:`sites`, is ``v``
``{"setting": "key", "in": ["a", "b"]}``          the setting is one of them
``{"flag": "name"}``                              the feature flag is on (see below)
``{"user_attr": "is_staff"}``                     ``is_staff``, ``is_superuser`` or
                                                  ``is_authenticated`` is true. No other
                                                  attribute can be read
``{"all": [...]}``                                every condition holds (an empty list does)
``{"any": [...]}``                                one of them holds (an empty list does not)
``{"not": {...}}``                                the condition does not hold
===============================================  ===========================================

Settings are text: ``equals`` and ``in`` compare a number by its text
(``3`` is ``"3"``) and a boolean, ignoring case, as ``"true"``/``"false"``. A
setting that does not exist matches nothing.

The example of the contract:

.. code:: json

    {"all": [
      {"perm": "ventas.view_pedido"},
      {"auth": "es_supervisor"},
      {"any": [{"group": "Finanzas"}, {"setting": "modo", "equals": "abierto"}]},
      {"not": {"flag": "beta_reportes"}}
    ]}

.. code:: python

    from djgentelella.authorization import evaluate_condition, validate_condition

    evaluate_condition(condition, request)            # None => True
    evaluate_condition(condition, request, pedido)    # with an object
    validate_condition(condition)                     # [] or [Error(path, message)]
    validate_condition(condition, '$.columns[2].condition')

* ``evaluate_condition(None, ...)`` is ``True``: no condition.
* An **invalid** condition is ``False``, and is logged.
* The **anonymous user** is evaluated like any other: ``perm``, ``group`` and
  ``user_attr`` are false for them, ``not`` turns that around. ``request=None``
  is an anonymous user in the global scope.
* ``validate_condition(cond, path='$', *, check_names=True)`` returns the
  ``djgentelella.designs.jsonschema.Error`` list -- ``(path, message)`` tuples,
  the same the design engine reports -- with the JSON path of each problem,
  for instance ``$.all[1].any[0].auth: unknown authorization 'x'``. With
  ``check_names=False`` the authorization names are not looked up.
* Conditions nest up to 32 levels.

Outside a request
-----------------

Flows run by the system, timers, background jobs and automations have a user
and a Site but no request. ``ConditionRequest(user=None, site=None)`` is the
public way to evaluate conditions, authorizations and flags **on behalf of a
user** there:

.. code:: python

    from djgentelella.authorization import ConditionRequest, evaluate_condition

    request = ConditionRequest(user=automation.run_as, site=automation.site)
    for row in rows:
        if evaluate_condition(automation.condition, request, row):
            ...

* ``user`` is who the condition is evaluated for. ``None`` is the system,
  which counts as an anonymous user: ``perm``, ``group`` and ``user_attr``
  are false for it.
* ``site`` is the Site whose scope applies -- settings, flags and groups by
  Site (``GT_SITE_GROUPS_RESOLVER``) --: a ``Site``, its id, or ``None`` for
  the global scope. Pass the Site of the job: without it, Site rules fall
  back to the global values. An id of no Site (one that was deleted, say)
  raises ``ValueError`` instead of falling back to the global scope.
* It carries what authorization functions usually read of a request:
  ``user``, ``site``, empty ``GET``, ``POST``, ``COOKIES`` and ``META``,
  ``method = None`` and ``path = ''``; ``is_condition_request`` is ``True``.
  An authorization that needs more of a real request should check for it.
* The per-request cache of authorizations (``cache=True``) lives on the
  object: reuse one ``ConditionRequest`` for many rows of the same user, and
  build a new one when the user, the Site or the data the authorizations read
  change.

The flows engine builds one on its own for the conditions of a run without a
request (see :doc:`flows`).


Views
=====

Django
------

.. code:: python

    from djgentelella.authorization import ConditionRequiredMixin, condition_required


    class Tablero(ConditionRequiredMixin, TemplateView):
        condition = {'any': [{'group': 'Finanzas'}, {'user_attr': 'is_superuser'}]}


    class PedidoDetalle(ConditionRequiredMixin, DetailView):
        condition = {'auth': 'es_dueno'}

        def get_condition_object(self):
            return self.get_object()


    @condition_required({'flag': 'beta_reportes'})
    def reporte_beta(request):
        ...

An anonymous user who fails goes to the login page; a signed-in one gets a
403 (``AccessMixin``, as ``PermissionRequiredMixin`` does).
``condition_required(..., raise_exception=True)`` gives everyone the 403. A
mixin without a condition raises ``ImproperlyConfigured``; the decorator
refuses an invalid condition when the module is imported.

Django REST framework
---------------------

.. code:: python

    from djgentelella.authorization import ConditionPermission


    class PedidoViewSet(viewsets.ModelViewSet):
        permission_classes = [ConditionPermission]
        conditions_by_action = {
            'list': {'perm': 'ventas.view_pedido'},
            'retrieve': {'auth': 'es_dueno'},
            'create': {'all': [{'perm': 'ventas.add_pedido'},
                               {'flag': 'pedidos_abiertos'}]},
        }

The view declares ``condition`` (every action) or ``conditions_by_action``.
Restrictive by default:

* an action missing from ``conditions_by_action`` is refused; on a plain
  ``APIView`` the action is the HTTP method, lowercase (``'get'``, ``'post'``);
* a view that declares neither is refused;
* the condition is evaluated without an object in ``has_permission`` and again
  with the object in ``has_object_permission``, so an authorization that
  decides per object should accept ``obj=None`` at the view level.


Templates
=========

.. code:: django

    {% load gtauthorization %}

    {% if_condition column.condition %}<th>Total</th>{% endif_condition %}
    {% if_condition '{"perm": "ventas.change_pedido"}' pedido %}
        <a href="...">Editar</a>
    {% else %}
        <span>Solo lectura</span>
    {% endif_condition %}

    {% if_flag "beta_reportes" %}...{% else %}...{% endif_flag %}

    {% if request|authorized:"es_supervisor" %}...{% endif %}
    {% authorized_for "es_dueno" pedido as puede %}
    {% condition_holds condition pedido as visible %}
    {% flag_on "beta_reportes" as beta %}

``if_condition`` takes a dict or its JSON text, and an optional object. All of
them read ``request`` from the context (the user and the Site); without it the
user is anonymous and the scope global.


Menus
=====

``MenuItem.condition`` is a nullable JSON field. An item is shown when the
user has **all** its permissions (as before) **and** its condition holds. An
item without a condition behaves as it always did; a hidden item hides its
children. The menu admin validates the condition when saving, unknown
authorizations included.

.. code:: python

    MenuItem.objects.create(title='Reportes beta', url_name='reportes_beta',
                            category='sidebar', is_reversed=True,
                            condition={'flag': 'beta_reportes'})


Feature flags
=============

A flag is a :class:`~djgentelella.models.GentelellaSettings` row whose key is
``flag.<name>``, so it follows the Site rule of :doc:`sites`: the value of the
current Site wins, then the global one; without either the flag is **off**.

.. code:: python

    from djgentelella.authorization import flag_enabled, set_flag

    set_flag('beta_reportes', True)                      # global
    set_flag('beta_reportes', False, site=site_ventas)   # off on that Site
    set_flag('beta_reportes', None, site=site_ventas)    # back to the global value
    flag_enabled('beta_reportes', request)               # the request's Site
    flag_enabled('beta_reportes', site=site_ventas)

* ``set_flag`` stores ``"true"`` or ``"false"``; a row written by hand counts
  as on with ``1``, ``true``, ``yes`` or ``on`` (any case).
* A name has letters, digits, ``_``, ``-`` and ``.``, up to 95 characters;
  anything else raises ``ValueError``.
* ``flag_value(name, site=None)`` is the raw value of one scope (``None`` when
  nothing is stored there), and ``flag_names()`` lists every flag stored.
* In conditions: ``{"flag": "beta_reportes"}``; in templates, ``{% if_flag %}``.

The **settings admin** (``Gentelella settings``) has a *Feature flags* link: a
table with one row per flag and one column per scope -- global and each Site --
where each cell can be turned on, off or, for a Site, back to inheriting the
global value. Seeing it needs the view or change permission of
``GentelellaSettings``; toggling needs the change permission.


Roles by Site
=============

The ``group`` node asks ``site_groups(user, site)`` which groups of the user
count in the current Site. By default that is every group of the user. A
project with roles per application (djodo's applications) plugs its own rule
with a setting:

.. code:: python

    # settings.py
    GT_SITE_GROUPS_RESOLVER = 'ventas.roles.site_groups'

    # ventas/roles.py
    def site_groups(user, site):
        """Groups (a queryset or any iterable of Group) valid on ``site``."""
        ...

The groups are read once per request.


Designs and flows
=================

* A node of a design document takes ``props.condition`` or
  ``meta.condition`` (not both). The engine validates it when publishing,
  keeps it out of the props the component sees, and for each request leaves
  out the nodes whose condition does not hold -- their children and media
  with them -- and answers 404 on their endpoints. See :doc:`designs`.
* Flow transitions and ``switch`` cases take a condition dict. Without a
  request it is evaluated for the run's user (anonymous for the system) and
  Site; ``publish_definition`` rejects an invalid one. See :doc:`flows`.


Settings
========

``GT_SITE_GROUPS_RESOLVER`` (unset)
    Dotted path (or callable) of ``function(user, site)`` returning the groups
    of the user valid on the Site. Unset: all the user's groups.
