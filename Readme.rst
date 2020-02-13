Django Gentelella widgets
############################

This app helps you to integrate Django apps with `Gentelella <https://colorlib.com/polygon/gentelella/index.html>`_ building extra widgets for forms and speciall methods to render forms in templates.

Installation
________________

Installing from repository (not in pip yet).

.. code:: bash

   pip install git+https://github.com/luisza/django-gentelella-widgets.git#egg=djgentelella

When pip is ready you can do

.. code:: bash

   pip install djgentelella

Configure your settings

.. code:: bash

    INSTALLED_APPS = [ ..
        'djgentelella',
        'mptt',
    ]

Run migrations 

.. code:: bash

    python manage.py migrate

Create statics files downloading from internet (you need to install requests for this step).

.. code:: bash

     pip install requests
     python manage.py loaddevstatic
     
Usage
_________


In forms 

.. code:: python

    from djgentelella.forms.forms import CustomForm
    from djgentelella.widgets import core as genwidgets

    class myform(CustomForm, forms.ModelForm):
        class Meta:
            model = MyObject
            fields = '__all__'
            widgets = {
                'name': genwidgets.TextInput,
                'borddate': genwidgets.DateInput,
                'email': genwidgets.EmailMaskInput
            }

In templates working with forms

.. code:: html

     {{ form.as_plain }}
     {{ form.as_inline }}
     {{ form.as_horizontal }}

In templates using base template

.. code:: html

    {% extends 'gentelella/base.html' %}
    
Take a look this file to note the template block that you can overwrite

widgets
__________

There is several widgets implemented this is a list of what you can use

- TextInput
- NumberInput
- EmailInput
- URLInput
- PasswordInput
- Textarea
- TextareaWysiwyg (not working yet)
- DateInput
- DateTimeInput
- TimeInput
- CheckboxInput
- YesNoInput
- Select  (jquery select2)
- SelectMultiple (jquery select2)
- SelectTail
- SelectMultipleTail
- RadioSelect
- NullBooleanSelect
- CheckboxSelectMultiple
- SplitDateTimeWidget (not ready)
- SplitHiddenDateTimeWidget (not ready)
- SelectDateWidget (not ready)
- PhoneNumberMaskInput
- DateMaskInput
- DateTimeMaskInput
- EmailMaskInput
- DateRangeTimeInput
- DateRangeInput




