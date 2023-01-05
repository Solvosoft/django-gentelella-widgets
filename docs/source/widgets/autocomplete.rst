AutoCompleteSelect and AutocompleteSelectMultiple widgets
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. image:: ../_static/autocomplete.png

2 requirements must be achieved to use these widgets


- Create a lookup channel in ``app/gtselects.py`` based in the model we want to use as options in the widget.
- Replace default widget in form with ``AutocompleteSelect`` or ``AutocompleteSelectMultiple``.


-------------------------------------
Defining Lookups for usage in widgets
-------------------------------------
An example on how a lookup must be defined:

.. code:: python

    from djgentelella.groute import register_lookups
    from djgentelella.views.select2autocomplete import BaseSelect2View
    from yourapp.models import models

    @register_lookups(prefix="person", basename="personbasename")
    class PersonGModelLookup(BaseSelect2View):
        model = models.Person
        fields = ['name']

Based in above example we need:

- A decorator named register_lookups defined above the lookup class that receives two parameters:
    - A prefix, which is basically the model name in lowcaps
    - A basename, which is a meaningful name that will help you differentiate between multiple lookups
- A class that inherits from the custom class BaseSelect2View which is responsible of creating an url that exposes the model data in a way the widget urderstands it, so to make it works the class needs:
    - A model to work with.
    - A list of fields from the model that the inherited class will use as filtering options when returning data to the widget.

If a more customized class is desired the next options can be overwritten to achieve it:

 - ref_field: can be used to select a specific field from the model with a list behavior (manytomanyfield or fields with choices) and use it to filter options.
 - ref_name: combined with ref_field, this field receives a list of strings that will be evaluated if any of its elements is contained in the ref_field field.
 - text_separator:  if provided, the class will use it to generate a list separated with the given value from result data.
 - text_wrapper: if provided, the class will wrap each element of the result query with the value given.
 - order_by: if provided, the class will used the given field to order the result query, the default field is the model pk.

-----------------
Usage in forms
-----------------

In model based form:

.. code:: python

    from djgentelella.widgets.selects import AutocompleteSelect, AutocompleteSelectMultiple
    from djgentelella.forms.forms import GTForm
    class PeopleGroupForm(GTForm, forms.ModelForm):
        class Meta:
            model = models.PeopleGroup
            fields = '__all__'
            widgets = {
                'name': TextInput,
                'people': AutocompleteSelectMultiple("personbasename"),
                'comunities': AutocompleteSelectMultiple("comunitybasename"),
                'country': AutocompleteSelect('countrybasename')
            }

As noticed in above example, the last steps are:
 - Replace the default widget with ``AutocompleteSelect`` or ``AutocompleteSelectMultiple`` (this may vary depending of the kind of form used).
 - Send the basename we provided in the lookup class decorator (see previous example) to the widget and it's ready for usage!


----------------------
Widget inside modals
----------------------

Select2 has problems for deal with forms inside modals, but it has an attribute to work with modals, so you can add `data-dropdownparent` as attr
for example

.. code:: html

    <div id="mymodal" class="modal" tabindex="-1">
        <div class="modal-body">
           {{form.has_horizontal}}
        </div>
    <div>

in forms.py

.. code:: python

