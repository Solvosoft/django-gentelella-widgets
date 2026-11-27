Lists of values (LOVs)
######################

A LOV is a named list of options, as in Oracle APEX: a function that returns a
queryset or a list of ``(value, label)``, served as json, edited with a select2
and validated on the server. A LOV can depend on other fields, which makes
selects that cascade: country, then province, then canton.

The value of each option is the pk for a queryset of models, the first column
for a ``values_list('code', 'name')`` or a ``values()`` queryset, and the first
item of each ``(value, label)`` of a list. Validation looks the value up the
same way, so it accepts exactly the values the select offers.

-----------------
Registering
-----------------

Put them in ``gtlovs.py`` in any installed app; it is discovered like
``gtcharts.py``:

.. code:: python

    # myapp/gtlovs.py
    from djgentelella.lov import register_lov

    @register_lov('paises')
    def paises(request, q=''):
        return Pais.objects.filter(nombre__icontains=q)

    @register_lov('provincias', depends_on=['pais'])
    def provincias(request, pais=None, q=''):
        if not pais:
            return Provincia.objects.none()
        return Provincia.objects.filter(pais=pais, nombre__icontains=q)

    @register_lov('estados', login_required=False)
    def estados(request, q=''):
        return [('A', 'Abierto'), ('C', 'Cerrado')]

* The function receives the request, one keyword per ``depends_on`` (``None``
  when empty) and the search text ``q``.
* It returns a queryset (value: ``pk``, label: ``str(obj)``) or a list of
  ``(value, label)`` pairs (or plain values).
* ``perms=['app.view_model']`` requires those permissions;
  ``login_required=True`` is the default, ``login_required=False`` (and no
  ``perms``) opens it to anonymous users. ``page_size`` defaults to 20.
* A repeated name replaces the previous LOV. ``get_lov(name)`` returns it.

-----------------
The endpoint
-----------------

``gtapis/lov/<name>/?q=&page=&pais=`` (url name ``gt-lov``) answers in the
select2 format::

    {"results": [{"id": "sj", "text": "San José"}], "pagination": {"more": false}}

404 for an unknown LOV, 403 without login or permissions, 400 for a page that
is not a positive integer.

Parent values come from the browser and are not validated before they reach
the function. When building or running the result raises ``ValueError``,
``TypeError``, ``OverflowError`` or ``ValidationError`` (``?pais=abc`` with
``filter(pais=pais)`` on an integer foreign key) the LOV counts as empty: the
endpoint answers ``{"results": [], ...}`` and ``LOVChoiceField`` rejects the
value with ``invalid_choice``, never a 500. Other exceptions are bugs of the
LOV and still propagate.

------------------
Widgets and fields
------------------

.. code:: python

    from djgentelella.fields.lov import LOVChoiceField, LOVMultipleChoiceField

    class DireccionForm(GTForm, forms.ModelForm):
        pais = LOVChoiceField('paises')
        provincia = LOVChoiceField('provincias')
        canton = LOVChoiceField('cantones', required=False)
        etiquetas = LOVMultipleChoiceField('etiquetas', required=False)

``LOVChoiceField`` renders ``LOVSelect`` (``LOVMultipleChoiceField``,
``LOVSelectMultiple``), a select2 that asks the endpoint as the user types and
sends the current values of the parent fields with every request. When a
parent changes, the select is emptied and reloads (the ``refresh`` dynamic
action), so a canton cannot outlive its province. It works in formsets and
modals; the parents are found by the form prefix.

On the server the field checks that the value is in the LOV **computed with
the parent values that came with the form**: a province of another country is
rejected. It returns the value as a string; ``coerce=int`` converts it.

Only the selected value is rendered as ``<option>``, with its label taken from
the LOV. During validation and that rendering the LOV runs with
``request=None`` unless the form has a ``request`` attribute.

When the LOV parameter and the form field have different names, map them:

.. code:: python

    provincia = LOVChoiceField('provincias', parents={'pais': 'country'})

The widgets can be used alone, ``LOVSelect('provincias')``; the prefix is then
taken from the widget's own name.

-----------------
Translated labels
-----------------

A ``LOVTranslation`` (LOV, value, language, label) replaces the label of a
value while its language is active, in the endpoint, the widgets and the
fields. ``register_lov(..., all_values=fn)`` lists every value of a LOV that
depends on its parents for the translation screen. See :doc:`translations`.

Who registered it
-----------------

``register_lov(..., owner='djodo.app.ventas')`` labels a LOV with its owner,
a free string: ``get_lovs(owner=...)`` lists only that owner's and
``get_lov(name).owner`` reads it (``''`` for a LOV without one). It is only a
label, like the ``tags`` of a pipeline process: it changes neither who may
open the LOV nor its Site.

-----------------
Not yet
-----------------

LOVs stored in the database (a ``StaticLOV`` model per Site) are not part of
this version.
