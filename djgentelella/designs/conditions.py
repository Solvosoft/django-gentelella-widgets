"""Conditions inside a component with data: per column and per action
(conditions of :mod:`djgentelella.authorization`).

A node's own condition (``props.condition``) hides it whole; the engine
applies it (:mod:`djgentelella.designs.engine`). Inside a table the design can
also say which columns and which actions exist for whom::

    "column_conditions": {"price": {"perm": "demoapp.change_product"}},
    "action_conditions": {"destroy": {"group": "Supervisors"}}

* a column whose condition does not hold is not shown, and its API leaves it
  out: not in the rows, not in the detail, and it cannot be searched,
  filtered or ordered by;
* an action whose condition does not hold has no button, and its API answers
  403.

The conditions are evaluated for the request and, on a page about one object
(``meta.parent``), with that object when the component's endpoints carry it
(an inline table and its facets): the same one the node conditions of the
page get. A component whose API does not know the object (a table of every
row, a classic CRUD) evaluates them without it, on the page and in the API.

**Per row.** The condition of an action on one row of a table (``update``,
``destroy``, ``retrieve``: the build's ``row_actions``) that names an
authorization (``{"auth": ...}``, a function of the request *and the
object*) is evaluated with each row instead::

    "action_conditions": {"update": {"auth": "is_owner"}}

Each row of the API says in its ``actions`` whether it has the button, and
the action on a row it does not hold for answers 403. The page keeps the
action's modal: whether a row offers it is the row's business. The other
conditions -- and those of ``create``, which has no row -- are evaluated
once, as above.

An inline table is not evaluated per row: its conditions, those of the row
actions included, get the object of the page like every other condition of
that page, so an authorization written for the parent keeps receiving it.
"""

from django.utils.translation import gettext as _

from djgentelella.authorization import evaluate_condition, validate_condition

__all__ = ['CONDITION', 'about_object', 'conditions_schema', 'check_conditions',
           'condition_object', 'denied', 'hidden_columns', 'row_conditions',
           'row_denied', 'without_hidden']

#: The schema of one condition: :func:`validate_condition` checks it.
CONDITION = {'x-widget': 'condition'}


def conditions_schema(title, keys=None):
    """The schema of a ``{name: condition}`` prop; ``keys`` limits the names."""
    schema = {'type': 'object', 'x-widget': 'conditions', 'title': title,
              'additionalProperties': CONDITION}
    if keys is not None:
        schema['additionalProperties'] = False
        schema['properties'] = {key: CONDITION for key in keys}
    return schema


def check_conditions(rctx, path, conditions, names, what):
    """Validate a ``{name: condition}`` prop; the valid ones, as a dict.

    ``names`` are the names it may hold (the columns the component shows,
    the actions it has); ``what`` says what they are, for the errors.
    """
    result = {}
    for name, cond in (conditions or {}).items():
        where = '%s.%s' % (path, name)
        if name not in names:
            rctx.error(where, _('%(name)r is not a %(what)s of this component '
                                '(%(names)s)') % {
                'name': name, 'what': what, 'names': ', '.join(names) or '-'})
            continue
        errors = validate_condition(cond, where)
        if errors:
            rctx.errors.extend(errors)
            continue
        result[name] = cond
    return result


def hidden_columns(build, request, obj=None):
    """The columns of ``build`` whose condition does not hold for
    ``request`` (and ``obj``)."""
    return {name for name, cond in (build.column_conditions or {}).items()
            if not evaluate_condition(cond, request, obj)}


def about_object(cond):
    """Whether the condition ``cond`` names an authorization (``auth``), the
    node that is given the object, anywhere inside it."""
    if not isinstance(cond, dict):
        return False
    if 'auth' in cond:
        return True
    for key in ('all', 'any'):
        if isinstance(cond.get(key), list) and any(
                about_object(item) for item in cond[key]):
            return True
    return about_object(cond.get('not'))


def row_conditions(build):
    """``{action: condition}`` of the conditions of ``build`` evaluated per
    row: those of its ``row_actions`` that are :func:`about_object`. None in
    an inline table (``build.inline``), whose conditions get the object of
    the page (:func:`condition_object`)."""
    if getattr(build, 'inline', False):
        return {}
    row_actions = getattr(build, 'row_actions', ())
    return {name: cond for name, cond in (build.action_conditions or {}).items()
            if name in row_actions and about_object(cond)}


def denied(build, request, obj=None):
    """The actions of ``build`` whose condition does not hold for
    ``request`` (and ``obj``); those evaluated per row
    (:func:`row_conditions`) are left to :func:`row_denied`."""
    per_row = row_conditions(build)
    return {name for name, cond in (build.action_conditions or {}).items()
            if name not in per_row and not evaluate_condition(cond, request, obj)}


def row_denied(build, request, row):
    """The actions of ``build`` refused on ``row``: its
    :func:`row_conditions` that do not hold for ``request`` with that row."""
    return {name for name, cond in row_conditions(build).items()
            if not evaluate_condition(cond, request, row)}


def condition_object(build, request):
    """The object the conditions inside ``build`` are evaluated with: the
    one of the page (``request.gtdesign_parent``) for a build whose
    endpoints carry it (``build.inline``), ``None`` otherwise."""
    if not getattr(build, 'inline', False):
        return None
    return getattr(request, 'gtdesign_parent', None)


def without_hidden(names, hidden):
    """``names`` (fields, or orderings such as ``'-price'`` or
    ``'category__name'``) without those over a ``hidden`` column."""
    return [name for name in names
            if not isinstance(name, str)
            or name.lstrip('-?').split('__')[0] not in hidden]
