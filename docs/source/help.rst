===========
Help System
===========

Django Gentelella Widgets includes a contextual help system that allows you to provide inline documentation for your forms and views. Help content is stored in the database and can be managed through the admin interface or API.


Help Model
==========

The ``Help`` model stores contextual help content that can be associated with specific views and form fields.

Fields
------

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Field
     - Type
     - Description
   * - ``id_view``
     - CharField
     - Identifier for the view (typically the Django URL name from ``resolver_match.view_name``)
   * - ``question_name``
     - CharField
     - Identifier for the specific form field or question (matches the field's label or name)
   * - ``help_title``
     - CharField
     - Title displayed in the help panel
   * - ``help_text``
     - TextField
     - Detailed help content (supports HTML)


Creating Help Content
=====================

Via Django Admin
----------------

The ``Help`` model is registered with Django admin. To add help content:

1. Navigate to Django Admin
2. Go to Djgentelella > Helps
3. Click "Add Help"
4. Fill in the fields:
   - **id_view**: The URL name of the view (e.g., ``'myapp:form_view'``)
   - **question_name**: The field identifier (e.g., ``'email'`` or ``'Date of Birth'``)
   - **help_title**: A brief title for the help entry
   - **help_text**: The detailed explanation


Programmatically
----------------

.. code:: python

    from djgentelella.models import Help

    Help.objects.create(
        id_view='myapp:user_create',
        question_name='email',
        help_title='Email Address',
        help_text='Enter a valid email address. This will be used for account verification and notifications.'
    )

    Help.objects.create(
        id_view='myapp:user_create',
        question_name='password',
        help_title='Password Requirements',
        help_text='''
            <p>Your password must:</p>
            <ul>
                <li>Be at least 8 characters long</li>
                <li>Contain at least one uppercase letter</li>
                <li>Contain at least one number</li>
                <li>Contain at least one special character</li>
            </ul>
        '''
    )


Help API
========

The help system provides a REST API for managing help content.

Endpoint
--------

Register the API endpoint in your ``urls.py``:

.. code:: python

    from django.urls import path, include
    from rest_framework.routers import DefaultRouter
    from djgentelella.widgets.helper import HelperWidgetView

    router = DefaultRouter()
    router.register('help', HelperWidgetView, basename='help')

    urlpatterns = [
        path('', include(router.urls)),
    ]

API Methods
-----------

**GET /help/**
    List all help entries. Supports filtering.

**GET /help/?id_view={view_name}**
    Filter help entries by view name.

**GET /help/?question_name={field_name}**
    Filter help entries by question/field name.

**GET /help/?id_view={view_name}&question_name={field_name}**
    Get help for a specific field in a specific view.

**POST /help/**
    Create a new help entry.

**PUT /help/{id}/**
    Update an existing help entry.

**DELETE /help/{id}/**
    Delete a help entry.

Response Format
---------------

.. code:: json

    {
        "id": 1,
        "id_view": "myapp:user_create",
        "question_name": "email",
        "help_title": "Email Address",
        "help_text": "Enter a valid email address..."
    }


PalleteWidget
=============

The ``PalleteWidget`` is a menu widget that provides an interactive help panel in the sidebar footer.

Configuration
-------------

Add the PalleteWidget to your menu:

.. code:: python

    from django.urls import reverse
    from djgentelella.models import MenuItem

    MenuItem.objects.create(
        title='',
        url_name='djgentelella.menu_widgets.palette.PalleteWidget',
        category='sidebarfooter',
        is_reversed=False,
        reversed_kwargs=None,  # Optional: custom permissions
        reversed_args=reverse('help'),  # Help API URL
        is_widget=True,
        icon='fa fa-question-circle',
        only_icon=True
    )

Parameters
----------

**reversed_args**
    The URL to the help API endpoint (from ``reverse('help')``).

**reversed_kwargs**
    Optional comma-separated list of permission strings to override defaults. If not specified, uses:

    - ``djgentelella.add_help``
    - ``djgentelella.change_help``
    - ``djgentelella.view_help``
    - ``djgentelella.delete_help``

Features
--------

The PalleteWidget provides:

- **Collapsible help panel**: Click the icon to expand/collapse
- **Draggable and resizable**: Users can position and resize the panel
- **Context-aware**: Automatically filters help by current view
- **CRUD operations**: Users with permissions can add, edit, and delete help entries directly from the panel


User Interface
==============

Help Panel
----------

When the PalleteWidget is configured, a help icon appears in the sidebar footer. Clicking it reveals a collapsible panel that:

1. Shows help entries relevant to the current view
2. Allows users to browse and search help content
3. Provides add/edit/delete buttons for users with appropriate permissions

Question Mark Icons
-------------------

Forms using djgentelella widgets can display question mark icons next to field labels. Clicking these icons highlights the corresponding help entry in the help panel.

Add/Edit/Delete
---------------

Users with appropriate permissions see additional controls:

- **Add**: Create new help entries for the current view
- **Edit**: Modify existing help content
- **Delete**: Remove help entries


Permissions
===========

The help system uses Django's permission framework. Required permissions:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Permission
     - Description
   * - ``djgentelella.view_help``
     - View help content (required for all users)
   * - ``djgentelella.add_help``
     - Create new help entries
   * - ``djgentelella.change_help``
     - Edit existing help entries
   * - ``djgentelella.delete_help``
     - Delete help entries

Assigning Permissions
---------------------

.. code:: python

    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType
    from djgentelella.models import Help

    # Get permissions
    content_type = ContentType.objects.get_for_model(Help)
    add_perm = Permission.objects.get(
        content_type=content_type,
        codename='add_help'
    )
    change_perm = Permission.objects.get(
        content_type=content_type,
        codename='change_help'
    )

    # Assign to user
    user.user_permissions.add(add_perm, change_perm)

    # Or assign to group
    group.permissions.add(add_perm, change_perm)


Complete Example
================

Here's a complete setup for the help system:

**urls.py:**

.. code:: python

    from django.urls import path, include
    from rest_framework.routers import DefaultRouter
    from djgentelella.widgets.helper import HelperWidgetView

    router = DefaultRouter()
    router.register('help', HelperWidgetView, basename='help')

    urlpatterns = [
        path('api/', include(router.urls)),
    ]

**Management command to create help:**

.. code:: python

    from django.core.management.base import BaseCommand
    from djgentelella.models import Help

    class Command(BaseCommand):
        help = 'Create help content for forms'

        def handle(self, *args, **options):
            # User registration form help
            Help.objects.get_or_create(
                id_view='myapp:register',
                question_name='username',
                defaults={
                    'help_title': 'Username',
                    'help_text': 'Choose a unique username. It must be 3-30 characters and can contain letters, numbers, and underscores.'
                }
            )

            Help.objects.get_or_create(
                id_view='myapp:register',
                question_name='email',
                defaults={
                    'help_title': 'Email',
                    'help_text': 'Enter your email address. We will send a verification link.'
                }
            )

            self.stdout.write(self.style.SUCCESS('Help content created'))

**Menu setup:**

.. code:: python

    from django.urls import reverse
    from djgentelella.models import MenuItem

    # Add help widget to sidebar footer
    MenuItem.objects.create(
        title='Help',
        url_name='djgentelella.menu_widgets.palette.PalleteWidget',
        category='sidebarfooter',
        is_reversed=False,
        reversed_args=reverse('help-list'),  # DRF router URL
        is_widget=True,
        icon='fa fa-question-circle',
        only_icon=True,
        position=99
    )
