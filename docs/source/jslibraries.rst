======================
JavaScript Libraries
======================

Django Gentelella Widgets bundles several JavaScript libraries that are automatically available when using the base template. These libraries are loaded via ``loaddevstatic`` and bundled into vendor files.


HTMX
====

`HTMX <https://htmx.org/>`_ is a library that allows you to access modern browser features directly from HTML, without writing JavaScript. It enables AJAX requests, CSS transitions, WebSockets, and Server-Sent Events using HTML attributes.

Version: Included in vendor bundle

Basic Usage
-----------

HTMX uses ``hx-*`` attributes to define behavior:

.. code:: html

    <!-- Load content via AJAX -->
    <button hx-get="/api/data/" hx-target="#result">
        Load Data
    </button>
    <div id="result"></div>

    <!-- Submit form via AJAX -->
    <form hx-post="/api/submit/" hx-swap="outerHTML">
        <input type="text" name="name">
        <button type="submit">Submit</button>
    </form>

Common Attributes
-----------------

**Request Attributes:**

- ``hx-get`` - Issue a GET request to the URL
- ``hx-post`` - Issue a POST request
- ``hx-put`` - Issue a PUT request
- ``hx-patch`` - Issue a PATCH request
- ``hx-delete`` - Issue a DELETE request

**Target & Swap:**

- ``hx-target`` - CSS selector for element to update with response
- ``hx-swap`` - How to swap content (``innerHTML``, ``outerHTML``, ``beforeend``, ``afterend``, etc.)
- ``hx-select`` - Select specific content from response

**Triggers:**

- ``hx-trigger`` - Event that triggers the request (default: ``click`` for buttons, ``change`` for inputs)

Examples
--------

**Load content on page load:**

.. code:: html

    <div hx-get="/api/stats/" hx-trigger="load">
        Loading...
    </div>

**Infinite scroll:**

.. code:: html

    <div hx-get="/api/items/?page=2"
         hx-trigger="revealed"
         hx-swap="afterend">
    </div>

**Search with debounce:**

.. code:: html

    <input type="search"
           name="q"
           hx-get="/api/search/"
           hx-trigger="keyup changed delay:500ms"
           hx-target="#search-results">

**Delete with confirmation:**

.. code:: html

    <button hx-delete="/api/item/1/"
            hx-confirm="Are you sure?"
            hx-target="closest tr"
            hx-swap="outerHTML">
        Delete
    </button>

**Include CSRF token (Django):**

.. code:: html

    <body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
        <!-- All HTMX requests will include CSRF token -->
    </body>

HTMX with Django Views
----------------------

HTMX works seamlessly with Django views. Return HTML fragments:

.. code:: python

    from django.shortcuts import render

    def partial_list(request):
        items = Item.objects.all()
        # Return only the fragment, not full page
        return render(request, 'partials/item_list.html', {'items': items})

Detect HTMX requests:

.. code:: python

    def my_view(request):
        if request.headers.get('HX-Request'):
            # HTMX request - return partial
            return render(request, 'partials/content.html')
        # Regular request - return full page
        return render(request, 'full_page.html')

Reference
---------

For complete documentation, see `htmx.org <https://htmx.org/>`_.


SweetAlert2
===========

`SweetAlert2 <https://sweetalert2.github.io/>`_ is a beautiful, responsive, customizable replacement for JavaScript's popup boxes.

Version: Included in vendor bundle (CSS and JS)

Basic Usage
-----------

.. code:: javascript

    // Simple alert
    Swal.fire('Hello World!')

    // Alert with title and text
    Swal.fire({
        title: 'Success!',
        text: 'Your action was completed.',
        icon: 'success'
    })

    // Confirmation dialog
    Swal.fire({
        title: 'Are you sure?',
        text: "You won't be able to revert this!",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Yes, delete it!',
        cancelButtonText: 'Cancel'
    }).then((result) => {
        if (result.isConfirmed) {
            // User confirmed
        }
    })

Icon Types
----------

- ``success`` - Green checkmark
- ``error`` - Red X
- ``warning`` - Yellow exclamation
- ``info`` - Blue info icon
- ``question`` - Blue question mark

Example from djgentelella
-------------------------

Used in the Trash feature for restore confirmation:

.. code:: javascript

    Swal.fire({
        icon: 'success',
        title: gettext('Success'),
        text: gettext('Item restored successfully'),
        confirmButtonText: gettext('Accept'),
    })

Reference
---------

For complete documentation, see `sweetalert2.github.io <https://sweetalert2.github.io/>`_.


Chart.js
========

`Chart.js <https://www.chartjs.org/>`_ is a simple yet flexible JavaScript charting library. djgentelella provides Django integration through chart widgets.

Version: Included in vendor bundle (CSS and JS)

For detailed usage with Django, see :doc:`appwidgets/charts`.

Basic Usage
-----------

.. code:: javascript

    const ctx = document.getElementById('myChart').getContext('2d');
    const myChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Red', 'Blue', 'Yellow'],
            datasets: [{
                label: '# of Votes',
                data: [12, 19, 3],
                backgroundColor: [
                    'rgba(255, 99, 132, 0.2)',
                    'rgba(54, 162, 235, 0.2)',
                    'rgba(255, 206, 86, 0.2)'
                ]
            }]
        }
    });

Available Chart Types
---------------------

- ``bar`` / ``horizontalBar`` - Bar charts
- ``line`` - Line charts
- ``pie`` / ``doughnut`` - Circular charts
- ``scatter`` - Scatter plots
- ``radar`` - Radar charts
- ``polarArea`` - Polar area charts

Reference
---------

For complete documentation, see `chartjs.org <https://www.chartjs.org/>`_.


PDF.js
======

`PDF.js <https://mozilla.github.io/pdf.js/>`_ is Mozilla's PDF viewer built with HTML5. It's used in djgentelella for the digital signature widget to display and interact with PDF documents.

Version: 4.6.82 (included in vendor bundle)

Usage in djgentelella
---------------------

PDF.js is primarily used internally by the digital signature widget (``firmador_digital``) to render PDF documents for signing. The viewer allows users to:

- View PDF documents in the browser
- Navigate between pages
- Place signature fields on the document

For digital signature functionality, see :doc:`widgets/firmador_digital`.

Reference
---------

For complete documentation, see `mozilla.github.io/pdf.js <https://mozilla.github.io/pdf.js/>`_.
