BreadcrumbNav
^^^^^^^^^^^^^^^^^

The hierarchical path that fills ``{% block breadcrumbs %}`` in
``gentelella/base.html`` and ``gentelella/plain.html``, which had shipped empty
since the theme was ported.

There are two halves and they cooperate:

* **Server-rendered.** A view that puts ``breadcrumbs`` in its context gets the
  path drawn by ``gentelella/blocks/breadcrumb.html`` before javascript runs.
  Pages that do not are unaffected: the include renders nothing.

  .. code:: python

     context['breadcrumbs'] = [
         {'label': 'Demo', 'href': '/'},
         {'label': warehouse.name},
     ]

* **Client-side.** ``BreadcrumbNav`` takes the same node over when the path has
  to change without a request.

  .. code:: javascript

     const crumbs = new BreadcrumbNav('gt-breadcrumb', {
         levels: [{label: 'Warehouse'}],
         onNavigate: (level, index) => console.log(level, index)
     });
     crumbs.push({label: 'Row 2'});
     crumbs.truncateTo(0);

API
"""

``set(levels)``, ``push(level)``, ``pop()``, ``truncateTo(index)`` (keeps
``0..index`` and returns what it dropped, so a host can undo), ``get(index)``,
``length``, ``destroy()``. Clicking a level fires ``bn:navigate`` with
``{nav, level, index}`` and calls ``onNavigate``; with ``autoTruncate`` (the
default) it also drops the levels after the one clicked.

A level is ``{id, label, icon?, href?}``. Without ``href`` the level renders as a
button, not an anchor: navigation is a callback, and an ``<a href="#">`` is a
broken link for anyone using a screen reader or middle-clicking.

Collapsing
""""""""""

When the trail does not fit, everything between the first and the last level
moves into a dropdown behind an ellipsis. There are only two states, expanded
and collapsed, never an iterative squeeze: collapsing changes the width that
decided to collapse, so a finer algorithm thrashes.

.. note::
   ``base.js`` is generated. After changing the widget run
   ``python manage.py createbasejs``.
