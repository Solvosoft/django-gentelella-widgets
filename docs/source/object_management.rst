CRUDAL For Models using modals
==================================

This functionality aims to integrate the following features that are generic to most models. The intention is to provide a view that lists objects using a table with multiple customizable filters and buttons for different actions, in established positions.
To perform the following actions, aspects of HTML that are resolved with templates, aspects of JavaScript that are resolved with a configuration object, and API-level actions that are resolved by implementing Django Rest Framework's ModelViewset APIs and some simple extra actions must be taken into consideration.

- **C** reate:  An object is created through a form.
- **R** etrieve: Displays information about an object using a `squirrelly`_ template language.
- **U** pdate: The information of an existing object loads a form and sends it to update an object.
- **D** elete:  An object is deleted through a form.
- **A** ctions: Extra actions to be performed on the instance, these actions do not include CRUDL actions, but are created by the developer.
- **L** ist:  Object information is tabulated using a `datatables`_, leaving the actions to be performed in the last column.

.. _squirrelly: https://squirrelly.js.org/
.. _datatables: https://datatables.net/

A set of templates is provided that can be used integrated into the code.

- `gentelella/blocks/modal_template.html`: Allows the creation of a modal for creating and updating a model.
- `gentelella/blocks/modal_template_detail.html`: Displays a modal with the title and detail according to the model instance.
- `gentelella/blocks/modal_template_delete.html`: Displays a modal for deleting an object.

In `demo/demoapp/templates/object_management.html` there is a good example of how to use the templates.
In `demo/demoapp/object_management/views.py` there is an example of a view and how to provide forms.

At the JavaScript level, the `ObjectCRUD` function allows the manipulation of the modals created with the templates, as well as handling all JavaScript-level actions.
For its configuration, the CRUDAL URLs must be provided; in the case of Delete, Detail, and Destroy, the value `/0/` will be changed to the id of the instance.


.. code:: javascript

    var object_urls = {
        list_url: "URL to obtain data for the table",
        destroy_url: "URL to delete the object",
        detail_url: "URL route to get the object detail to display",
        detail_template_url: "URL of the template to use to display the object, loaded only once on initialization",
        update_values_url: "URL to get the values of an update form",
        create_url: "URL to send the data for object creation",
        update_url: "URL to send the data for object update"
    }

.. note:: Not providing a URL disables the action or functionality.

The modal IDs defined in the templates must be added, and it is important to ensure that there are no collisions of modal names.

.. code:: javascript

    var obj_modalids = {
        create: "#create_obj_modal",
        update: "#update_obj_modal",
        detail: "#detail_obj_modal",
        destroy: "#delete_obj_modal",
    }

One way to disable CRUD functionality if desired is not to provide the key with the modal ID.
Additional actions to be performed can be configured.

.. code:: javascript

    var obj_actions = {
         table_actions: [],   // List of model-level actions
         object_actions: [],  // List of instance-level actions
         title: gettext('Actions'), // Title of the column
         className:  "no-export-col" //  CSS class to use for the column
    }

All these and other configurations are grouped in the configuration.

.. code:: javascript

    let objconfig={
        urls: object_urls, // URLs to use
        datatable_element:  "#object_table", // ID of the table to render the data
        modal_ids: obj_modalids, // Modal IDs to use
        actions: obj_actions,  // Additional actions
        datatable_inits: datatable_inits, // Datatable configuration to customize the table
        add_filter: true, // Shows a set of filters as the first row in the table
        relation_render: {'country': 'name' },  // Allows presenting related objects
        delete_display: data => data['name']  // Function that returns an abbreviated representation of the object.
    }

It is worth noting that there are several configurations and events that allow customizing the information that is sent and received from the API.

.. code:: javascript

    let ocrud=ObjectCRUD("setmeunique", objconfig)
    ocrud.init();



It is worth noting that there are several configurations and events that allow customizing the information that is sent and received from the API.

At the API level, it is recommended to see the example API view in `demo/demoapp/object_management/viewset.py` .


Events
-----------

**ObjectCRUD  events**:

- 'update_data':  It's call after success request of instance data, pass de data getter and expect returned the data user to fill the field form

Must be look like this in config object.

.. code:: javascript

        events: {
             'update_data': function(data){ return data; }
        },

**BaseDetailModal events**:

- 'update_detail_event': It's call before submit data to api to get object detail field for update
- 'form_submit_template': It's call before submit data to api to get the template.
- 'form_submit_instance': It's call before submit data to api to get the instance data.
- 'form_error_instance':  It's call when happens errors on request to get data instance.
- 'form_error_template':  It's call when happens errors on request to get template.

Must be look like this in config object.

.. code:: javascript

        gt_form_modals: {
             'detail': {
                "events": {
                   'update_detail_event': function(data){ return data},
                   'form_submit_template': function(data){ return data},
                   'form_submit_instance': function(data){ return data},
                   'form_error_instance': function(errors){},
                   'form_error_template': function(errors){}
                }
            }
        }

**GTBaseFormModal events**:

- 'form_submit':  It's call before set extra data on the request.
- 'success_form': It's call after success request is processed
- 'error_form':  It's call when happens an error

Must be look like this in config object.

.. code:: javascript

        gt_form_modals: {
            'create': {
                "events": {
                    'form_submit': function(instance){ return {} },
                    'success_form': function(data){},
                    'error_form': function(errors){}
                          }
            },
            'update': { /** same here*/ },
            'destroy': {  /** same here*/ }
        }
        ,

**gtCreateDataTable events:**

It's call before return the request parameters, pass the parameter to be send, and require return of data

.. code:: javascript

        datatable_inits : {
          "events": {
            filter: function(data){
                            return data;
                    }
            }
        }

Custom Actions
-----------------------

It is possible to register custom actions to the CRUDL object, these actions are by default registered in the
actions column of each table object.
Actions for objects must be registered in the `object_actions` list, the `in_action_column` allow not displayed icon
in the actions column so you must called in another column.


.. code:: javascript

    object_actions: [
      {
        'name': "mycustomaction",  // Action identification, must be unique
        'action': 'mycustomaction', // Name of the function to call to process the action.
        'title': 'Human descriptor', // Tittle display when mouse is over
        'in_action_column': false, // The action must be displayed in the actions column
        'i_class': 'fa fa-plus', // clase a utilizar para el ícono de la acción.
      }
    ]

To provide action function implementation you can append to `ObjectCRUD` instance properties

.. code:: javascript

    let ocrud=ObjectCRUD("setmeunique", objconfig)
    ocrud.mycustomaction = function(obj, action){ /** Js stuff */}
    ocrud.init();


Additionally, if you don't want to provide a function and instead prefer to make a request to the server, you can register an action like this.

.. code:: javascript

    object_actions: [
      {
        'name': "mydo_action",  // Action identification, must be unique
        'action': 'mydo_action', // Name of the function to call to process the action.
        'in_action_column': false, // The action must be displayed in the actions column
        'i_class': 'fa fa-plus', // clase a utilizar para el ícono de la acción.
        'method': 'POST',
        'title': ''  // Display when mouse is over the icon
        'data_fn': function(data){ return data; }, // Preprocess data before send to server, it's required return data
        'error_fn' function(errors) {} // Optional manage the form errors if exists
      }
    ]


Render actions on  custom column
---------------------------------------

Djgentelella allows registering a field and rendering the obtained values to present the actions at the end of the representation

.. code:: javascript

    datatable_inits = {
      columns: [
        {data: "mycolumn", name: "mycolumn", title: "title", type: "string",  visible: true, render:  gt_show_actions("setmeunique")},
      ]

It's important to mention that the unique name registered in `ObjectCRUD` must be used in the `gt_show_actions` function.

The function expects an API response like this:

.. code:: javascript

    {
        'title': 'One string representation of the object, it could be html ether',
        'actions': [
            {
                'name': 'mycustomaction',  // Action identification
                'i_class': 'fa fa-plus'  // Class used to show the action
            }
        ]
    }


API class helpers
---------------------------------------

BaseObjectManagement
'''''''''''''''''''''''''

A class that extends the `viewsets.ModelViewSet` class to provide custom behavior for CRUD (create, read, update, and delete) operations on Django models and other custom actions (get_values_for_update).

Attributes
----------
- `serializer_class`: a dictionary containing the names of the view methods (such as "list" or "create") as keys and the corresponding serialization classes as values.
- `pagination_class`: the pagination class that will be used to paginate query results. In this case, the `LimitOffsetPagination` class is used, which will paginate results based on the limit and offset values provided in the HTTP request.
- `filter_backends`: a tuple containing the filtering classes that will be used to filter query results. In this case, three classes are used: `DjangoFilterBackend`, `SearchFilter`, and `OrderingFilter`. These classes are used together to allow users to search, filter, and sort query results.
- `operation_type`: a string indicating the type of operation being performed in the view. This value is used in some of the methods to customize the HTTP response that is sent to the user.

Methods
-------
- `get_serializer_class(self)`: returns the serialization class that should be used for the current view action. It checks the `serializer_class` dictionary to see if a serialization class has been provided for the current action, and returns it if it has. If no serialization class has been provided, it falls back to the default behavior of returning the serialization class defined in the `serializer_class` attribute.
- `list(self, request, *args, **kwargs)`: is called when the view is accessed with an HTTP GET request. It filters the queryset based on the request parameters, paginates the results, and returns a JSON response containing the paginated data along with some metadata about the total number of records and the filtering parameters used.
- `retrieve(self, request, *args, **kwargs)`: is called when the view is accessed with an HTTP GET request that includes a primary key in the URL. It retrieves the object with the specified primary key, serializes it, and returns a JSON response containing the serialized data.
- `get_values_for_update(self, request, *args, **kwargs)`: is a custom action that can be called with an HTTP GET request on an object detail endpoint. It retrieves the object with the specified primary key, serializes it, and returns a JSON response containing data used to fill update form on frontend.
- `detail_template(self, request, *args, **kwargs)`: is a custom action that can be called with an HTTP GET request on a list endpoint. It returns a JSON response containing a template that can be used to render details of objects. Must be compatible with squirrelly.js


AuthAllPermBaseObjectManagement
'''''''''''''''''''''''''''''''''''''

A class that extends the `BaseObjectManagement` class to provide authentication and permission checking for CRUD operations on Django models.


Attributes

- `authentication_classes`: a tuple containing the authentication classes that will be used to authenticate requests. In this case, `TokenAuthentication` and `SessionAuthentication` are used.
- `perms`: a dictionary containing the names of the view methods (such as "list" or "create") as keys and the corresponding permission classes as values. These permission classes are used to check if the user has the required permissions to perform the requested action.
- `permission_classes`: a tuple containing the permission classes that will be used to check if the user has the required permissions to perform the requested action. In this case, the `AllPermissionByAction` class is used, which checks that the user has all the permissions specified in the `perms` dictionary for the requested action.

.. code:: python

    class MyClass(AuthAllPermBaseObjectManagement):
        perms = {
            'list': ['auth.view_user'],
            'create': ['auth.add_user'],
            'update': ['auth.change_user'],
            'delete': ['auth.delete_user'],
            'retrieve': ['auth.view_user'],
            'get_values_for_update': ['auth.change_user']
        }

AuthAnyPermBaseObjectManagement
'''''''''''''''''''''''''''''''''''

A class that extends the `BaseObjectManagement` class to provide authentication and permission checking for CRUD operations on Django models.

Attributes

- `authentication_classes`: a tuple containing the authentication classes that will be used to authenticate requests. In this case, `TokenAuthentication` and `SessionAuthentication` are used.
- `perms`: a dictionary containing the names of the view methods (such as "list" or "create") as keys and the corresponding permission classes as values. These permission classes are used to check if the user has the required permissions to perform the requested action.
- `permission_classes`: a tuple containing the permission classes that will be used to check if the user has the required permissions to perform the requested action. In this case, the `AnyPermissionByAction` class is used, which checks that the user has at least one of the permissions specified in the `perms` dictionary for the requested action.

.. code:: python

    class MyClass(AuthAnyPermBaseObjectManagement):
        perms = {
            'list': ['auth.view_user'],
            'create': ['auth.add_user'],
            'update': ['auth.change_user'],
            'delete': ['auth.delete_user'],
            'retrieve': ['auth.view_user'],
            'get_values_for_update': ['auth.change_user']
        }
