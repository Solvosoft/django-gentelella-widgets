Widgets
==========

You can create a form like this

.. code:: python

    from djgentelella.forms.forms import CustomForm
    from djgentelella.widgets import core as genwidgets
    class ExampleForm(CustomForm):
        your_email = forms.EmailField(widget=genwidgets.EmailInput)

Like a others Django widgets, you can pass this widgets on Meta form class

.. code:: python

    class ExampleForm(CustomForm, forms.ModelForm):
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

Notification widget
^^^^^^^^^^^^^^^^^^^
This widget allows to store and send email notifications
.. automodule:: djgentelella.notification.widgets
   :members:

Not all widgets are good supported yet.