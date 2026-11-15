Dynamic actions
###############

Dynamic actions are what Oracle APEX calls *Dynamic Actions*: a field that
appears, a value that is computed, a select that reloads, all declared in
Python on the form. A small runtime in ``base.js`` runs them in the browser,
so the page needs no JavaScript of its own.

.. code:: python

    from django import forms
    from django.utils.translation import gettext_lazy as _

    from djgentelella.forms.dynamic import When
    from djgentelella.forms.forms import GTForm

    class PedidoForm(GTForm, forms.ModelForm):
        dynamic_actions = [
            When('tipo').equals('empresa').show('razon_social', 'cedula_juridica')
            .require('cedula_juridica'),
            When('pais').changes().refresh('provincia'),
            When('cantidad', 'precio').changes()
            .set_value('total', server='calc_total'),
            When('descuento').gt(50).confirm(_('¿Descuento mayor a 50%?')),
            When('estado').in_('cerrado', 'anulado').disable('*')
            .enable('observaciones'),
        ]

        def calc_total(self, data):          # runs on the server
            return {'total': ...}

The demo has the whole thing at ``/dynamic_actions/``: a page, the same form
in a formset (``/dynamic_actions/formset/``) and in ObjectCRUD modals
(``/dynamic_actions/crud/``).

-----------------
Rules
-----------------

A rule is ``When(*fields)``, one trigger and one or more actions, chained.

Triggers
========

========================= ====================================================
``changes()``             Every action runs each time one of the fields
                          changes.
``on_load()``             Every action runs once, when the form starts.
                          ``When().on_load()`` takes no fields.
``equals(value)``         Condition: the field equals ``value`` (as text; a
                          multiple select equals when it contains it, a
                          checkbox compares with ``True``/``False``).
``not_equals(value)``     Condition: the opposite.
``in_(*values)``          Condition: equals one of ``values``.
``gt(n)`` / ``lt(n)``     Condition: the field, as a number, is greater/less
                          than ``n``. Not a number is never true.
``is_empty()``            Condition: empty, unchecked or nothing selected.
``is_checked()``          Condition: a checkbox checked (or a group of
                          checkboxes with something checked).
========================= ====================================================

With more than one field, a condition must hold for all of them.

**Conditions are evaluated on load and on every change.** While a condition
holds, the *reversible* actions are applied; when it stops holding they are
undone, in reverse order. So ``disable('*').enable('observaciones')`` disables
everything but *observaciones* while the order is closed, and enables
everything again when it is reopened, without a second rule. The other
actions (``set_value``, ``refresh``, ``confirm``, ``call``) run only when a
user change makes the condition true.

Actions
=======

=============================================== ==============================
``show(*fields)`` / ``hide(*fields)``           The field and its label (its
                                                ``.gtformfield`` box).
                                                Reversible.
``enable(*fields)`` / ``disable(*fields)``      The ``disabled`` property.
                                                Reversible. A disabled field
                                                is not submitted.
``require(*fields)``                            The ``required`` property, and
                                                ``gt-required`` on the label.
                                                Reversible.
``add_class(css, *fields)`` /                   A class on the input itself.
``remove_class(css, *fields)``                  Reversible.
``set_value(field, value)``                     A constant.
``set_value(field, from_field='other')``        A copy of another field.
``set_value(field, server='method')``           What the form method answers
                                                on the server (below).
``refresh(*fields)``                            Empties a dependent select so
                                                it reloads; a LOV select2 asks
                                                its endpoint again.
``confirm(message)``                            Asks; if the user declines the
                                                field goes back to its previous
                                                value and the rest of the rule
                                                does not run.
``call(name, *args)``                           A JavaScript function
                                                registered with
                                                ``document.gtdynamic.register``.
=============================================== ==============================

``'*'`` means every visible field of the form except the rule's own fields
(a rule that disables "everything" when ``estado`` is closed would otherwise
disable ``estado`` and lock the user out). It works with show, hide, enable,
disable, require and the class actions.

Field names are checked when the form renders: a name the form class does not
have raises ``ImproperlyConfigured``; a field the instance removed in
``__init__`` is skipped (a rule watching it is dropped).

``require()`` is a hint for the browser. Validate on the server as usual, in
``clean()``.

Rules may feed each other: a ``set_value`` (or a ``refresh``, or the
``setValue`` of a ``call`` function) fires ``change`` on its field, which runs
the rules that watch it. A field whose value does not change runs nothing.
Each change of the user starts a cascade that goes at most ten changes deep,
also when they come from a promise or a server answer, so two rules that keep
changing each other stop there (with a warning in the console).

-------------------------------
Values computed on the server
-------------------------------

``set_value(field, server='calc_total')`` posts the current values of the form
to ``gtapis/dynamic/`` (url name ``gt-dynamic-action``) and sets every field in
the answer:

.. code:: python

    def calc_total(self, data):
        # data: {field: raw value}, unprefixed, strings as the browser sent them
        cantidad = int(data.get('cantidad') or 0)
        precio = Decimal(data.get('precio') or 0)
        return {'total': cantidad * precio}

* The rendered form carries a reference ``(form path, method)`` signed with
  ``django.core.signing``; an altered or foreign token is refused (403).
* The method has to be declared in a ``set_value(server=...)`` of the class
  attribute ``dynamic_actions``, both when the form renders and when the
  endpoint runs: no other method of the form, and no other class, can be
  reached. The form must be a module level class.
* The token is stamped with the time it was rendered and expires after
  ``GT_DYNAMIC_ACTIONS_MAX_AGE`` seconds (default ``43200``, 12 hours;
  ``None`` never expires): an expired token answers 403 and the page has to be
  reloaded.
* When the form has a ``request`` attribute with an authenticated user
  (``form.request = request`` in the view), the token is bound to that user:
  another user, or an anonymous client, gets a 403 with it.
* Who may run the method is decided by the classmethod
  ``Form.dynamic_actions_has_permission(request, method)``. By default it asks
  for an authenticated user (``dynamic_actions_public = True`` on the form
  opens it to anyone) holding every permission of
  ``dynamic_actions_permissions = ['app.perm', ...]``. Override it to apply the
  same rule as the page that renders the form: the token alone only proves that
  someone, at some point, saw a page with the form. CSRF applies as to any POST.
* The instance is built with ``Form.dynamic_actions_instance(request)``, which
  is ``cls()``; override it when ``__init__`` needs arguments.
* Raising ``ValidationError`` answers 400 with ``{"errors": [...]}``. Keys of
  the answer that are not fields of the form are dropped.
* A body that is not ``{"token": str, "data": {field: scalar or list}}`` is a
  400.

-----------------
Where it runs
-----------------

GTForm adds a hidden ``<div class="gt-dynamic-actions" data-gt-dynamic='[...]'>``
at the end of every render (``as_plain``, ``as_inline``, ``as_horizontal``,
``as_grid``, ``{{ form }}``...), with the form prefix and its field list. A
form without ``dynamic_actions`` renders exactly as before.

The rules are not an attribute of the ``<form>`` tag because GTForm does not
render that tag, and a formset puts several forms, each with its own prefix,
inside a single ``<form>``. The runtime also reads ``data-gt-dynamic`` from a
``<form>`` element, for the templates described below.

The runtime listens to ``change`` (select2 fires it on the underlying select)
and to the date picker's ``dp.change``; an event that does not change the value
already handled does not run the rules again.

Fields are looked up by name (``<prefix>-<field>``) inside the closest
``<form>``, so each row of a formset and each modal of an ObjectCRUD page runs
its own rules. ``gt_find_initialize()`` starts the runtime, which is how a row
added by ``formset.js`` gets it; a form inside a bootstrap modal is evaluated
again every time the modal opens, after ObjectCRUD has filled it.

A template that renders the fields one by one, without ``{{ form }}``, can put
the rules on the form tag instead::

    <form method="post"{{ form.dynamic_actions_attrs }}> ... </form>

(not both: the rules would run twice).

``get_dynamic_actions()`` returns the rules an instance renders; override it to
drop some per user. Server methods still have to be in the class attribute.

-----------------
JavaScript API
-----------------

.. code:: javascript

    document.gtdynamic.register('mayusculas', function (ctx) {
        // ctx.form, ctx.scope (the <form>), ctx.prefix, ctx.rule, ctx.args,
        // ctx.event, ctx.field(name) -> jQuery, ctx.value(name),
        // ctx.setValue(name, value)
        ctx.setValue('nombre', String(ctx.value('nombre')).toUpperCase());
        // return false (or a promise of false) to stop the rest of the rule
    });

``document.gtdynamic.initialize(container)`` starts the rules of markup added
by hand, and ``document.gtdynamic.refresh(elements)`` empties selects the way
the ``refresh`` action does. A failed server call triggers ``gtdynamic:error``
on the form.

Everything that comes from the rules is set as data (``.val()``, ``.prop()``,
the ``text`` of the confirmation dialog), never as html.

See also :doc:`lov` for selects that cascade.
