Introduction
=============

Django Gentelella Widgets is a reusable Django application library that integrates Bootstrap 5 with various JavaScript libraries as Django widgets and form utilities.

What is Django Gentelella Widgets?
------------------------------------

Django Gentelella Widgets provides:

- **Bootstrap 5 Widgets** - Form widgets styled with Bootstrap 5 for consistent, modern UI
- **JavaScript Library Integration** - Select2, DataTables, TinyMCE, DateRangePicker, and more
- **CRUD Views** - Generic views for Create, Read, Update, Delete operations with permissions
- **DataTables Integration** - Server-side processing with filtering, pagination, and sorting
- **Rich Form Components** - Date pickers, file uploads, WYSIWYG editors, masked inputs

Key Features
--------------

**Forms & Widgets**

- GTForm base class with multiple render methods (horizontal, inline, plain, grid)
- 50+ widgets including selects, date pickers, file uploads, and more
- Autocomplete widgets with AJAX support
- Chunked file upload for large files
- Digital signature integration

**CRUD Operations**

- CRUDView for quick CRUD interface generation
- Permission checking (login required, model permissions)
- Customizable templates and forms
- Pagination and search support

**DataTables**

- Server-side processing for large datasets
- Column filtering and global search
- Automatic parameter translation between DataTables and DRF
- Custom render functions for cell formatting

**Additional Features**

- Blog system
- Notification system
- History/audit trail
- Trash/soft delete functionality
- Permission management UI

Requirements
--------------

- Python 3.11+
- Django 4.2+
- Django REST Framework

Quick Example
---------------

.. code:: python

    from django import forms
    from djgentelella.forms.forms import GTForm
    from djgentelella.widgets import core as genwidgets

    class ContactForm(GTForm, forms.Form):
        name = forms.CharField(widget=genwidgets.TextInput)
        email = forms.EmailField(widget=genwidgets.EmailInput)
        phone = forms.CharField(widget=genwidgets.PhoneNumberMaskInput)
        birth_date = forms.DateField(widget=genwidgets.DateInput)
        country = forms.ChoiceField(widget=genwidgets.Select, choices=[])
        message = forms.CharField(widget=genwidgets.Textarea)

In your template:

.. code:: html

    {% extends 'gentelella/base.html' %}

    {% block content %}
    <form method="post">
        {% csrf_token %}
        {{ form.as_horizontal }}
        <button type="submit" class="btn btn-primary">Submit</button>
    </form>
    {% endblock %}

Getting Started
-----------------

1. :doc:`installation` - Install and configure djgentelella
2. :doc:`demo` - Run the demo application to explore features
3. :doc:`forms` - Learn about GTForm and rendering options
4. :doc:`widgets/widgets` - Explore available widgets

License
---------

Django Gentelella Widgets is released under the MIT License.

Contributing
--------------

Contributions are welcome! Please visit the `GitHub repository <https://github.com/Solvosoft/django-gentelella-widgets>`_ to:

- Report issues
- Submit pull requests
- Request features

