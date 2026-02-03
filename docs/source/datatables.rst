DataTables
=============

Django Gentelella Widgets integrates DataTables.js with Django REST Framework for powerful server-side data tables with filtering, searching, pagination, and sorting.

Overview
-----------

The DataTables integration uses a three-tier architecture:

- **Backend**: Django REST Framework ViewSets with filtering and pagination
- **Frontend**: DataTables.js with server-side processing
- **Integration**: Custom JavaScript functions that bridge DRF and DataTables protocols

Quick Start
--------------

Here's a minimal example to get a DataTable working:

1. Create a ViewSet that returns data in DataTables format
2. Register the ViewSet in your URL router
3. Add a table element in your template
4. Initialize DataTables with JavaScript

.. code:: python

    # views.py
    from rest_framework import viewsets
    from rest_framework.response import Response
    from rest_framework.pagination import LimitOffsetPagination

    class PersonViewSet(viewsets.ModelViewSet):
        queryset = Person.objects.all()
        serializer_class = PersonSerializer
        pagination_class = LimitOffsetPagination

        def list(self, request, *args, **kwargs):
            queryset = self.filter_queryset(self.get_queryset())
            data = self.paginate_queryset(queryset)
            response = {
                'data': PersonSerializer(data, many=True).data,
                'recordsTotal': Person.objects.count(),
                'recordsFiltered': queryset.count(),
                'draw': request.GET.get('draw', 1)
            }
            return Response(response)

.. code:: html

    <!-- template.html -->
    <table id="my-table" class="table"></table>

    <script>
        createDataTable('#my-table', '{% url "api-person-list" %}', {
            columns: [
                {data: "name", name: "name", title: "Name", type: "string", visible: true},
                {data: "email", name: "email", title: "Email", type: "string", visible: true},
            ]
        }, addfilter=true);
    </script>


Backend Setup
----------------

ViewSet
""""""""""""

The ViewSet handles server-side processing including pagination, filtering, and ordering.

.. code:: python

    from rest_framework import viewsets
    from rest_framework.response import Response
    from rest_framework.pagination import LimitOffsetPagination
    from rest_framework.filters import SearchFilter, OrderingFilter
    from django_filters.rest_framework import DjangoFilterBackend

    class PersonViewSet(viewsets.ModelViewSet):
        queryset = Person.objects.all()
        serializer_class = PersonDataTableSerializer
        pagination_class = LimitOffsetPagination

        # Enable filtering backends
        filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)

        # Fields for global search (search box)
        search_fields = ['name', 'email', 'country__name']

        # Fields that can be ordered
        ordering_fields = ['name', 'num_children', 'born_date', 'last_time']
        ordering = ('-num_children',)  # Default ordering

        # FilterSet for column-specific filtering
        filterset_class = PersonFilterSet

        def list(self, request, *args, **kwargs):
            queryset = self.filter_queryset(self.get_queryset())
            data = self.paginate_queryset(queryset)

            response = {
                'data': data,
                'recordsTotal': Person.objects.count(),
                'recordsFiltered': queryset.count(),
                'draw': self.request.GET.get('draw', 1)
            }
            return Response(self.get_serializer(response).data)

Response Format
^^^^^^^^^^^^^^^^

The ``list()`` method must return a response matching the DataTables protocol:

.. code:: javascript

    {
        "data": [...],           // Array of row objects
        "recordsTotal": 1000,    // Total records before filtering
        "recordsFiltered": 250,  // Records after filtering
        "draw": 1                // Request counter (prevents out-of-order responses)
    }

Serializers
""""""""""""""""

You need two serializers: one for individual records and one for the DataTables response wrapper.

.. code:: python

    from rest_framework import serializers
    from .models import Person, Country

    class CountrySerializer(serializers.ModelSerializer):
        class Meta:
            model = Country
            fields = ['id', 'name']

    class PersonSerializer(serializers.ModelSerializer):
        # Nested serializer for ForeignKey fields
        country = CountrySerializer(read_only=True)

        # Computed field for action buttons
        actions = serializers.SerializerMethodField()

        def get_actions(self, obj):
            return {
                'edit_url': f'/person/{obj.pk}/update/',
                'delete_url': f'/person/{obj.pk}/delete/',
            }

        class Meta:
            model = Person
            fields = ['id', 'name', 'email', 'num_children', 'country',
                      'born_date', 'last_time', 'actions']

    class PersonDataTableSerializer(serializers.Serializer):
        """Wrapper serializer matching DataTables protocol"""
        data = serializers.ListField(child=PersonSerializer(), required=True)
        draw = serializers.IntegerField(required=True)
        recordsFiltered = serializers.IntegerField(required=True)
        recordsTotal = serializers.IntegerField(required=True)

FilterSet
""""""""""""""""

Use django-filter's FilterSet for column-specific filtering:

.. code:: python

    from django_filters import FilterSet, DateFromToRangeFilter
    from django_filters.widgets import DateRangeWidget
    from .models import Person

    class PersonFilterSet(FilterSet):
        # Date range filter
        born_date = DateFromToRangeFilter(
            widget=DateRangeWidget(attrs={'placeholder': 'YYYY-MM-DD'})
        )

        class Meta:
            model = Person
            fields = {
                'name': ['icontains'],        # Case-insensitive substring
                'num_children': ['exact'],     # Exact match
                'country__name': ['icontains'] # Filter on related field
            }

URL Configuration
""""""""""""""""""""

Register the ViewSet using DRF's router:

.. code:: python

    from rest_framework.routers import DefaultRouter
    from .views import PersonViewSet

    router = DefaultRouter()
    router.register('person', PersonViewSet, basename='api-person')

    urlpatterns = [
        path('api/', include(router.urls)),
    ]

This generates the following endpoints:

- ``GET /api/person/`` - List with filtering/pagination
- ``POST /api/person/`` - Create
- ``GET /api/person/{id}/`` - Retrieve
- ``PUT /api/person/{id}/`` - Update
- ``DELETE /api/person/{id}/`` - Delete


Frontend Setup
-----------------

HTML Structure
""""""""""""""""

The table element only needs an ID. DataTables builds the structure dynamically:

.. code:: html

    {% extends 'gentelella/base.html' %}

    {% block content %}
    <div class="card">
        <div class="card-body">
            <h2>People</h2>
            <table id="people-table" class="table table-bordered table-hover"></table>
        </div>
    </div>
    {% endblock %}

    {% block js %}
    <script>
        // DataTables initialization goes here
    </script>
    {% endblock %}

JavaScript Initialization
"""""""""""""""""""""""""""

Use ``createDataTable()`` to initialize the table:

.. code:: javascript

    var peopleTable = createDataTable(
        '#people-table',                    // Table selector
        '{% url "api-person-list" %}',      // API endpoint URL
        {
            columns: [
                {data: "name", name: "name", title: "Name", type: "string", visible: true},
                {data: "email", name: "email", title: "Email", type: "string", visible: true},
                {data: "num_children", name: "num_children", title: "Children", type: "number", visible: true},
                {data: "country", name: "country__name", title: "Country", type: "string",
                 render: selectobjprint({display_name: "name"})},
            ]
        },
        addfilter=true  // Add column filter inputs
    );

Function Signature
^^^^^^^^^^^^^^^^^^^

.. code:: javascript

    createDataTable(id, url, extraoptions={}, addfilter=false, formatDataTableParamsfnc=formatDataTableParams)

**Parameters:**

- ``id`` - CSS selector for the table element (e.g., ``'#my-table'``)
- ``url`` - API endpoint URL
- ``extraoptions`` - DataTables configuration options (including ``columns``)
- ``addfilter`` - If ``true``, adds filter inputs below column headers
- ``formatDataTableParamsfnc`` - Custom function to format request parameters

Column Configuration
""""""""""""""""""""""""

Each column in the ``columns`` array can have these properties:

.. code:: javascript

    {
        data: "country",                    // Property name in JSON response
        name: "country__name",              // Field name for filtering (Django lookup syntax)
        title: "Country",                   // Column header text
        type: "string",                     // Data type (affects filter UI)
        visible: true,                      // Show/hide column
        render: selectobjprint({            // Custom render function
            display_name: "name"
        }),
        orderable: true,                    // Enable sorting (default: true)
        searchable: true,                   // Enable searching (default: true)
    }

Column Types
^^^^^^^^^^^^^

The ``type`` property determines what filter widget appears:

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * - Type
     - Filter Widget
     - Description
   * - ``string``
     - Text input
     - Text search with ``icontains``
   * - ``number``
     - Number input
     - Numeric exact match
   * - ``boolean``
     - Select (Yes/No)
     - Boolean field filter
   * - ``date``
     - DateRangePicker
     - Date range selection
   * - ``select``
     - Static select
     - Predefined options
   * - ``select2``
     - AJAX Select2
     - Dynamic search options
   * - ``readonly``
     - None
     - No filter for this column

Select Column with Static Options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: javascript

    {
        data: "status",
        name: "status",
        title: "Status",
        type: "select",
        choices: [
            ["pending", "Pending"],
            ["approved", "Approved"],
            ["rejected", "Rejected"]
        ],
        visible: true
    }

Select2 Column with AJAX Search
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: javascript

    {
        data: "category",
        name: "category",
        title: "Category",
        type: "select2",
        url: "/api/categories/search/",  // Endpoint for Select2 AJAX
        multiple: false,                  // Allow multiple selection
        visible: true
    }


Render Functions
-------------------

Render functions format cell data for display.

Built-in Functions
""""""""""""""""""""

yesnoprint
^^^^^^^^^^^

Displays boolean values with icons:

.. code:: javascript

    {data: "is_active", name: "is_active", title: "Active", type: "boolean",
     render: yesnoprint}

Output: ``✓ Yes`` or ``✗ No``

objShowBool
^^^^^^^^^^^^

Alias for ``yesnoprint``.

emptyprint
^^^^^^^^^^^^

Shows ``--`` for null/empty values:

.. code:: javascript

    {data: "nickname", name: "nickname", title: "Nickname", type: "string",
     render: emptyprint}

selectobjprint
^^^^^^^^^^^^^^^

Displays a property from nested objects (for ForeignKey fields):

.. code:: javascript

    {data: "country", name: "country__name", title: "Country", type: "string",
     render: selectobjprint({display_name: "name"})}

Given response ``{"country": {"id": 1, "name": "USA"}}``, displays ``USA``.

gt_print_list_object
^^^^^^^^^^^^^^^^^^^^^

Displays a list of objects (for ManyToMany fields):

.. code:: javascript

    {data: "tags", name: "tags__name", title: "Tags", type: "string",
     render: gt_print_list_object("name")}

showlink
^^^^^^^^^

Creates a link button:

.. code:: javascript

    {data: "document_url", name: "document_url", title: "Document",
     render: showlink}

Output: ``<a href="..." class="btn btn-success">More</a>``

downloadlink
^^^^^^^^^^^^^

Creates a download link:

.. code:: javascript

    {data: "file_url", name: "file_url", title: "File",
     render: downloadlink}

objshowlink
^^^^^^^^^^^^^

Creates a link from structured data:

.. code:: javascript

    {data: "profile_link", name: "profile_link", title: "Profile",
     render: objshowlink}

Expects data format:

.. code:: javascript

    {
        url: "https://example.com/profile/1",
        class: "btn btn-primary",
        display_name: "View Profile"
    }

truncateTextRenderer
^^^^^^^^^^^^^^^^^^^^^

Truncates long text with tooltip:

.. code:: javascript

    {data: "description", name: "description", title: "Description",
     render: truncateTextRenderer(100)}  // Max 100 characters


Date and Time Handling
-------------------------

Frontend Display
""""""""""""""""""""

For proper date formatting, provide format strings from Django settings:

.. code:: html

    {% load timejs %}

    <script>
        document.date_format = "{% get_date_format %}";
        document.datetime_format = "{% get_datetime_format %}";
    </script>

Then use DataTables' built-in datetime renderer:

.. code:: javascript

    {
        data: "born_date",
        name: "born_date",
        title: "Born Date",
        type: "date",
        render: DataTable.render.date(),
        dateformat: document.date_format,
        visible: true
    },
    {
        data: "last_time",
        name: "last_time",
        title: "Last Updated",
        type: "date",
        render: DataTable.render.datetime(),
        dateformat: document.datetime_format,
        visible: true
    }

Backend Serializers
""""""""""""""""""""

DRF's default DateField fails on empty strings. Use the custom fields provided:

.. code:: python

    from djgentelella.serializers import GTDateField, GTDateTimeField

    class PersonSerializer(serializers.ModelSerializer):
        born_date = GTDateField(allow_empty_str=True)
        last_time = GTDateTimeField(allow_empty_str=True)

        class Meta:
            model = Person
            fields = '__all__'


Events and Customization
---------------------------

Filter Event
""""""""""""""""

Modify request parameters before sending:

.. code:: javascript

    createDataTable('#my-table', url, {
        columns: [...],
        events: {
            filter: function(data) {
                // Add custom parameter
                data.custom_param = 'value';
                return data;
            }
        }
    }, addfilter=true);

Custom Parameter Formatting
"""""""""""""""""""""""""""""

Override the default parameter translation:

.. code:: javascript

    function myFormatParams(dataTableParams, settings) {
        var data = {
            'page': Math.floor(dataTableParams.start / dataTableParams.length) + 1,
            'page_size': dataTableParams.length,
            'draw': dataTableParams.draw
        };

        // Add search
        if (dataTableParams.search.value) {
            data['q'] = dataTableParams.search.value;
        }

        return data;
    }

    createDataTable('#my-table', url, {columns: [...]}, true, myFormatParams);

Reload Table Data
""""""""""""""""""""

.. code:: javascript

    // Reload keeping current page
    peopleTable.ajax.reload(null, false);

    // Reload and go to first page
    peopleTable.ajax.reload();

Clear All Filters
""""""""""""""""""""

.. code:: javascript

    clearDataTableFilters(peopleTable, '#people-table');


Complete Example
-------------------

Here's a full implementation example:

Model
""""""""

.. code:: python

    # models.py
    from django.db import models

    class Country(models.Model):
        name = models.CharField(max_length=100)

        def __str__(self):
            return self.name

    class Person(models.Model):
        name = models.CharField(max_length=150)
        email = models.EmailField()
        num_children = models.IntegerField(default=0)
        country = models.ForeignKey(Country, on_delete=models.CASCADE)
        born_date = models.DateField()
        last_time = models.DateTimeField(auto_now=True)
        is_active = models.BooleanField(default=True)

Serializers
""""""""""""

.. code:: python

    # serializers.py
    from rest_framework import serializers
    from djgentelella.serializers import GTDateField, GTDateTimeField
    from .models import Person, Country

    class CountrySerializer(serializers.ModelSerializer):
        class Meta:
            model = Country
            fields = ['id', 'name']

    class PersonSerializer(serializers.ModelSerializer):
        country = CountrySerializer(read_only=True)
        born_date = GTDateField()
        last_time = GTDateTimeField()

        class Meta:
            model = Person
            fields = ['id', 'name', 'email', 'num_children', 'country',
                      'born_date', 'last_time', 'is_active']

    class PersonDataTableSerializer(serializers.Serializer):
        data = serializers.ListField(child=PersonSerializer())
        draw = serializers.IntegerField()
        recordsTotal = serializers.IntegerField()
        recordsFiltered = serializers.IntegerField()

FilterSet
""""""""""""

.. code:: python

    # filters.py
    from django_filters import FilterSet, DateFromToRangeFilter
    from .models import Person

    class PersonFilterSet(FilterSet):
        born_date = DateFromToRangeFilter()

        class Meta:
            model = Person
            fields = {
                'name': ['icontains'],
                'email': ['icontains'],
                'num_children': ['exact', 'gte', 'lte'],
                'country__name': ['icontains'],
                'is_active': ['exact'],
            }

ViewSet
""""""""""""

.. code:: python

    # views.py
    from rest_framework import viewsets
    from rest_framework.response import Response
    from rest_framework.pagination import LimitOffsetPagination
    from rest_framework.filters import SearchFilter, OrderingFilter
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import Person
    from .serializers import PersonSerializer, PersonDataTableSerializer
    from .filters import PersonFilterSet

    class PersonViewSet(viewsets.ModelViewSet):
        queryset = Person.objects.select_related('country').all()
        serializer_class = PersonDataTableSerializer
        pagination_class = LimitOffsetPagination
        filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
        search_fields = ['name', 'email', 'country__name']
        filterset_class = PersonFilterSet
        ordering_fields = ['name', 'num_children', 'born_date', 'last_time']
        ordering = ['-last_time']

        def list(self, request, *args, **kwargs):
            queryset = self.filter_queryset(self.get_queryset())
            data = self.paginate_queryset(queryset)
            response = {
                'data': data,
                'recordsTotal': Person.objects.count(),
                'recordsFiltered': queryset.count(),
                'draw': int(request.GET.get('draw', 1))
            }
            return Response(self.get_serializer(response).data)

        def get_serializer_class(self):
            if self.action == 'list':
                return PersonDataTableSerializer
            return PersonSerializer

URLs
""""""""

.. code:: python

    # urls.py
    from django.urls import path, include
    from rest_framework.routers import DefaultRouter
    from .views import PersonViewSet

    router = DefaultRouter()
    router.register('people', PersonViewSet, basename='api-person')

    urlpatterns = [
        path('api/', include(router.urls)),
        path('people/', TemplateView.as_view(template_name='people_list.html'), name='people-list'),
    ]

Template
""""""""""""

.. code:: html

    <!-- templates/people_list.html -->
    {% extends 'gentelella/base.html' %}
    {% load timejs %}

    {% block content %}
    <div class="card">
        <div class="card-header">
            <h3>People Directory</h3>
        </div>
        <div class="card-body">
            <table id="people-table" class="table table-bordered table-hover"></table>
        </div>
    </div>
    {% endblock %}

    {% block js %}
    <script>
        document.date_format = "{% get_date_format %}";
        document.datetime_format = "{% get_datetime_format %}";

        var peopleTable = createDataTable(
            '#people-table',
            '{% url "api-person-list" %}',
            {
                columns: [
                    {
                        data: "name",
                        name: "name",
                        title: gettext("Name"),
                        type: "string",
                        visible: true
                    },
                    {
                        data: "email",
                        name: "email",
                        title: gettext("Email"),
                        type: "string",
                        visible: true
                    },
                    {
                        data: "num_children",
                        name: "num_children",
                        title: gettext("Children"),
                        type: "number",
                        visible: true
                    },
                    {
                        data: "country",
                        name: "country__name",
                        title: gettext("Country"),
                        type: "string",
                        visible: true,
                        render: selectobjprint({display_name: "name"})
                    },
                    {
                        data: "born_date",
                        name: "born_date",
                        title: gettext("Born Date"),
                        type: "date",
                        dateformat: document.date_format,
                        render: DataTable.render.date(),
                        visible: true
                    },
                    {
                        data: "last_time",
                        name: "last_time",
                        title: gettext("Last Updated"),
                        type: "date",
                        dateformat: document.datetime_format,
                        render: DataTable.render.datetime(),
                        visible: true
                    },
                    {
                        data: "is_active",
                        name: "is_active",
                        title: gettext("Active"),
                        type: "boolean",
                        visible: true,
                        render: yesnoprint
                    }
                ],
                order: [[5, 'desc']]  // Default sort by last_time descending
            },
            addfilter=true
        );
    </script>
    {% endblock %}


Request/Response Flow
------------------------

Understanding how data flows between frontend and backend:

1. **User interacts** with table (pagination, sorting, filtering)
2. **DataTables.js** sends AJAX request with its protocol parameters
3. **formatDataTableParams()** converts to DRF-compatible format:

   .. code::

       DataTables             →  DRF
       start: 0               →  offset: 0
       length: 10             →  limit: 10
       search[value]: "john"  →  search: "john"
       order[0][column]: 0    →  ordering: "name" or "-name"
       order[0][dir]: "asc"

4. **DRF ViewSet** processes filters, search, ordering, pagination
5. **Response** returned in DataTables format:

   .. code:: javascript

       {
           "data": [{...}, {...}, ...],
           "recordsTotal": 1000,
           "recordsFiltered": 45,
           "draw": 1
       }

6. **DataTables.js** renders rows and updates pagination


API Reference
----------------

JavaScript Functions
""""""""""""""""""""""

createDataTable(id, url, extraoptions, addfilter, formatDataTableParamsfnc)
    Main initialization function for DataTables.

gtCreateDataTable(id, url, table_options)
    Lower-level initialization with full options control.

formatDataTableParams(dataTableParams, settings)
    Converts DataTables request format to DRF format.

addSearchInputsAndFooterDataTable(dataTable, tableId, columns)
    Adds filter input row below headers.

clearDataTableFilters(dataTable, tableId)
    Clears all column filters and reloads table.

yesnoprint(data, type, row, meta)
    Renders boolean as Yes/No with icons.

emptyprint(data, type, row, meta)
    Renders null/empty as ``--``.

selectobjprint(config)
    Returns render function for nested objects.

gt_print_list_object(display_name)
    Returns render function for object arrays.

showlink(data, type, row, meta)
    Renders URL as link button.

downloadlink(data, type, row, meta)
    Renders URL as download button.

objshowlink(data, type, row, meta)
    Renders structured link object.

objnode(data, type, row, meta)
    Renders structured data as custom HTML element.

truncateTextRenderer(maxChars)
    Returns render function that truncates text.

Python Classes
""""""""""""""""

.. autoclass:: djgentelella.serializers.GTDateField
   :members:

.. autoclass:: djgentelella.serializers.GTDateTimeField
   :members:

