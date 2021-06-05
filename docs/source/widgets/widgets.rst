Common Widgets
===============

All widgets here works like django widgets.

You can create a form like this

.. code:: python

    from djgentelella.forms.forms import GTForm
    from djgentelella.widgets import core as genwidgets
    class ExampleForm(GTForm):
        your_email = forms.EmailField(widget=genwidgets.EmailInput)

Like a others Django widgets, you can pass this widgets on Meta form class

.. code:: python

    class ExampleForm(GTForm, forms.ModelForm):
        class Meta:
            model = Mymodel
            widgets = {
                'email': genwidgets.EmailInput
            }

Common widgets
^^^^^^^^^^^^^^^^^^^^^
Available widgets are:

.. automodule:: djgentelella.widgets.core
   :members:

Trees widgets
^^^^^^^^^^^^^^^^^^^
Django Gentelella use MTPP for tree database representations

.. automodule:: djgentelella.widgets.trees
   :members:

Tinymce widgets
^^^^^^^^^^^^^^^^^^^
Available widget is:

.. automodule:: djgentelella.widgets.tinymce
   :members:


