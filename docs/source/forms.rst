Forms
##########

GTForm is the foundation of form management in Django Gentelella Widgets. It provides Bootstrap-compatible rendering methods and integrates seamlessly with the widget library.

-----------------
Basic Usage
-----------------

Inherit from ``GTForm`` instead of ``forms.Form``:

.. code:: python

    from django import forms
    from djgentelella.forms.forms import GTForm
    from djgentelella.widgets import core as genwidgets

    class ContactForm(GTForm, forms.Form):
        name = forms.CharField(widget=genwidgets.TextInput)
        email = forms.EmailField(widget=genwidgets.EmailInput)
        message = forms.CharField(widget=genwidgets.Textarea)

-----------------
With ModelForm
-----------------

GTForm can be combined with ModelForm:

.. code:: python

    from django import forms
    from djgentelella.forms.forms import GTForm
    from djgentelella.widgets import core as genwidgets

    class PersonForm(GTForm, forms.ModelForm):
        class Meta:
            model = Person
            fields = ['name', 'email', 'birth_date', 'country']
            widgets = {
                'name': genwidgets.TextInput,
                'email': genwidgets.EmailInput,
                'birth_date': genwidgets.DateInput,
                'country': genwidgets.Select,
            }

-----------------
Render Methods
-----------------

GTForm provides multiple rendering methods for Bootstrap layouts:

as_horizontal (default)
""""""""""""""""""""""""

Labels and inputs side by side in a horizontal layout. This is the default render type.

.. code:: html

    {{ form.as_horizontal }}

as_inline
""""""""""""

Labels appear inline with form fields.

.. code:: html

    {{ form.as_inline }}

as_plain
""""""""""""

Simple stacked layout with labels above inputs.

.. code:: html

    {{ form.as_plain }}

as_grid
""""""""""""

Custom grid layout allowing you to arrange fields in rows and columns.

.. code:: html

    {{ form.as_grid }}

----------------------
Specifying Render Type
----------------------

You can set the render type when creating the form instance:

.. code:: python

    # In your view
    form = ContactForm(render_type='as_inline')

Or set a default for the form class:

.. code:: python

    class ContactForm(GTForm, forms.Form):
        default_render_type = 'as_plain'

        name = forms.CharField(widget=genwidgets.TextInput)
        email = forms.EmailField(widget=genwidgets.EmailInput)

-----------------
Grid Layout
-----------------

The ``as_grid`` method allows custom field arrangement. Define the layout using ``grid_representation``:

.. code:: python

    from django import forms
    from djgentelella.forms.forms import GTForm
    from djgentelella.widgets import core as genwidgets

    class AddressForm(GTForm, forms.Form):
        # Define the grid layout: rows of columns of fields
        grid_representation = [
            # Row 1: Two columns with one field each
            [['first_name'], ['last_name']],
            # Row 2: Full width field
            [['address']],
            # Row 3: Three columns
            [['city'], ['state'], ['zip_code']],
            # Row 4: Two columns
            [['country'], ['phone']],
        ]

        first_name = forms.CharField(widget=genwidgets.TextInput)
        last_name = forms.CharField(widget=genwidgets.TextInput)
        address = forms.CharField(widget=genwidgets.TextInput)
        city = forms.CharField(widget=genwidgets.TextInput)
        state = forms.CharField(widget=genwidgets.TextInput)
        zip_code = forms.CharField(widget=genwidgets.TextInput)
        country = forms.ChoiceField(widget=genwidgets.Select, choices=[])
        phone = forms.CharField(widget=genwidgets.PhoneNumberMaskInput)

In your template:

.. code:: html

    {{ form.as_grid }}

The grid structure is:

.. code:: python

    grid_representation = [
        [['field1'], ['field2']],  # Row with 2 columns
        [['field3']],               # Row with 1 column (full width)
        [['field4'], ['field5'], ['field6']],  # Row with 3 columns
    ]

Each row is automatically sized based on the number of columns (Bootstrap grid system).

-----------------
Template Usage
-----------------

In your template, render the form using any method:

.. code:: html

    {% extends 'gentelella/base.html' %}

    {% block content %}
    <form method="post" enctype="multipart/form-data">
        {% csrf_token %}

        {# Choose one render method: #}
        {{ form.as_horizontal }}
        {# or {{ form.as_inline }} #}
        {# or {{ form.as_plain }} #}
        {# or {{ form.as_grid }} #}

        <button type="submit" class="btn btn-primary">Submit</button>
    </form>
    {% endblock %}

-----------------
FormSets
-----------------

Use ``GTFormSet`` for managing multiple forms:

.. code:: python

    from django.forms import formset_factory
    from djgentelella.forms.forms import GTForm, GTFormSet
    from djgentelella.widgets import core as genwidgets

    class ItemForm(GTForm, forms.Form):
        name = forms.CharField(widget=genwidgets.TextInput)
        quantity = forms.IntegerField(widget=genwidgets.NumberInput)
        price = forms.DecimalField(widget=genwidgets.FloatInput)

    ItemFormSet = formset_factory(ItemForm, formset=GTFormSet, extra=3)

In your view:

.. code:: python

    def items_view(request):
        if request.method == 'POST':
            formset = ItemFormSet(request.POST)
            if formset.is_valid():
                for form in formset:
                    # Process each form
                    pass
        else:
            formset = ItemFormSet()
        return render(request, 'items.html', {'formset': formset})

In your template:

.. code:: html

    <form method="post">
        {% csrf_token %}
        {{ formset.as_horizontal }}
        <button type="submit">Save</button>
    </form>

-----------------
Model FormSets
-----------------

Use ``GTBaseModelFormSet`` for model-based formsets:

.. code:: python

    from django.forms import modelformset_factory
    from djgentelella.forms.forms import GTForm, GTBaseModelFormSet
    from djgentelella.widgets import core as genwidgets

    class ProductForm(GTForm, forms.ModelForm):
        class Meta:
            model = Product
            fields = ['name', 'price', 'stock']
            widgets = {
                'name': genwidgets.TextInput,
                'price': genwidgets.FloatInput,
                'stock': genwidgets.NumberInput,
            }

    ProductFormSet = modelformset_factory(
        Product,
        form=ProductForm,
        formset=GTBaseModelFormSet,
        extra=1,
        can_delete=True
    )

-----------------
Complete Example
-----------------

Here's a comprehensive example combining multiple features:

.. code:: python

    from django import forms
    from djgentelella.forms.forms import GTForm
    from djgentelella.widgets import core as genwidgets
    from djgentelella.widgets.selects import AutocompleteSelect

    class OrderForm(GTForm, forms.ModelForm):
        # Custom grid layout
        grid_representation = [
            [['customer'], ['order_date']],
            [['shipping_address']],
            [['city'], ['state'], ['postal_code']],
            [['notes']],
        ]

        class Meta:
            model = Order
            fields = [
                'customer', 'order_date', 'shipping_address',
                'city', 'state', 'postal_code', 'notes'
            ]
            widgets = {
                'customer': AutocompleteSelect('customerbasename'),
                'order_date': genwidgets.DateInput,
                'shipping_address': genwidgets.TextInput,
                'city': genwidgets.TextInput,
                'state': genwidgets.Select,
                'postal_code': genwidgets.TextInput,
                'notes': genwidgets.Textarea,
            }

In your view:

.. code:: python

    def create_order(request):
        if request.method == 'POST':
            form = OrderForm(request.POST, render_type='as_grid')
            if form.is_valid():
                form.save()
                return redirect('order_list')
        else:
            form = OrderForm(render_type='as_grid')
        return render(request, 'order_form.html', {'form': form})

API Reference
"""""""""""""

.. automodule:: djgentelella.forms.forms
   :members:
