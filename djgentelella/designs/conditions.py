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
They are not evaluated per row.
"""

from djgentelella.authorization import evaluate_condition, validate_condition

__all__ = ['CONDITION', 'conditions_schema', 'check_conditions', 'condition_object',
           'denied', 'hidden_columns', 'without_hidden']

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
            rctx.error(where, '%r is not a %s of this component (%s)' % (
                name, what, ', '.join(names) or '-'))
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


def denied(build, request, obj=None):
    """The actions of ``build`` whose condition does not hold for
    ``request`` (and ``obj``)."""
    return {name for name, cond in (build.action_conditions or {}).items()
            if not evaluate_condition(cond, request, obj)}


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
