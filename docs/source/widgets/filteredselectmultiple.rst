FilteredSelectMultiple widget
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Two lists side by side -- available on the left, chosen on the right -- with a
filter box and arrows to move entries between them. It is the layout django
admin draws for ``filter_horizontal``, available to any form.

Both panels are plain ``<select multiple>``. The one on the right **is** the
form field, so what sits inside it when the form is submitted is what posts:
moving an entry is moving the ``<option>`` node, and there is no submit hook
that can be missed.

Files: ``djgentelella/widgets/selectmultiple.py``,
``gentelella/js/base/filteredselectmultiple.js``,
``gentelella/css/filteredselectmultiple.css`` and the template
``gentelella/widgets/filteredselectmultiple.html``.

.. note:: ``filteredselectmultiple.js`` is bundled into ``base.js``, so run
   ``python manage.py createbasejs`` after updating the library.

--------------------
Usage without an API
--------------------

With no ``url`` the options come from the field's own ``choices``. The template
renders every one of them inside the chosen select and the javascript moves the
unselected ones to the available panel, which means the field still works -- as
a plain multiple select -- when javascript is off.

.. code:: python

    from django import forms
    from djgentelella.forms.forms import GTForm
    from djgentelella.widgets.selectmultiple import FilteredSelectMultiple

    class LanguagesForm(GTForm, forms.Form):
        languages = forms.MultipleChoiceField(
            choices=[
                ('Compiled', [('c', 'C'), ('go', 'Go'), ('rs', 'Rust')]),
                ('Interpreted', [('py', 'Python'), ('rb', 'Ruby')]),
            ],
            widget=FilteredSelectMultiple(verbose_name='languages'),
        )

``optgroup`` is preserved: a group is mirrored on the other side when the first
of its options moves there, and dropped again when the last one leaves.

-----------------
Usage with an API
-----------------

Pass ``url`` with the ``basename`` of a lookup registered in
``app/gtselects.py``, exactly like the autocomplete widgets -- it is the same
``BaseSelect2View`` endpoint and the same JSON contract, documented under
*AutoCompleteSelect and AutocompleteSelectMultiple widgets*.

.. code:: python

    from djgentelella.groute import register_lookups
    from djgentelella.views.select2autocomplete import BaseSelect2View

    @register_lookups(prefix="person", basename="personbasename")
    class PersonGModelLookup(BaseSelect2View):
        model = models.Person
        fields = ['name']

.. code:: python

    class PeopleGroupForm(GTForm, forms.ModelForm):
        class Meta:
            model = PeopleGroup
            fields = ['name', 'people']
            widgets = {
                'name': genwidgets.TextInput,
                'people': FilteredSelectMultiple(
                    url='personbasename', verbose_name='people'),
            }

With an endpoint only the chosen options are rendered in the page; the
available panel is filled page by page as the user scrolls it, and the filter
box sends its text as ``term`` instead of filtering in the browser. Entries the
endpoint marks as ``disabled`` are shown but never move, and the ones already
chosen are never offered twice.

The widget works with a ``ManyToManyField`` and with any plain
``MultipleChoiceField``; nothing about it is tied to a relation.

-----------------------
Creating a new option
-----------------------

``add_url`` adds a ``+`` button that opens a modal with a form of your own. The
view answers ``GET`` with the rendered form and ``POST`` with the created
object, and the new entry lands in the available panel.

.. code:: python

    'people': FilteredSelectMultiple(url='personbasename', add_url='/person/add/'),

.. code:: python

    def person_add_view(request):
        if request.method == 'GET':
            html = render_to_string('myapp/person_modal.html',
                                    {'form': PersonForm(prefix='newperson')})
            return JsonResponse({'result': html})
        form = PersonForm(json.loads(request.body), prefix='newperson')
        if not form.is_valid():
            return JsonResponse({'error': form.errors}, status=400)
        person = form.save()
        return JsonResponse({'result': {'id': person.pk, 'text': str(person)}})

The modal body needs a ``<form>`` and a button with the class
``save_data_btn``. Give the form a ``prefix`` when its fields collide with the
ones of the surrounding form.

-----------------
Widget options
-----------------

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Option
     - Default
     - Description
   * - ``verbose_name``
     - the field name
     - Used in the two panel titles, *Available X* and *Chosen X*.
   * - ``url``
     - ``None``
     - ``basename`` of a lookup in ``app/gtselects.py``. Without it the widget
       works from the field's ``choices``.
   * - ``url_suffix``
     - ``'-list'``
     - Appended to ``url`` before reversing, as in the autocomplete widgets.
   * - ``url_args`` / ``url_kwargs``
     - ``[]`` / ``{}``
     - Extra arguments for the reverse, for endpoints that take a pk.
   * - ``add_url``
     - ``None``
     - Enables the ``+`` button and points it at the view that creates a new
       option.
   * - ``is_stacked``
     - ``False``
     - Puts one panel under the other instead of side by side. Below 576px the
       layout stacks anyway.

-----------------------
Several on one page
-----------------------

Every node the template renders takes its id from the id of the real select,
and the javascript registers each widget under that same id, so any number of
them coexist on a page. Two forms with a field of the same name still need a
``prefix``, as they would with any other widget:

.. code:: python

    form = PeopleGroupForm()
    other = PeopleGroupForm(prefix='second')

The demo at ``/filteredselect/`` shows both modes on one page.
