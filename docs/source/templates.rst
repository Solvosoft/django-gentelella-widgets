Using in templates
====================

Basic usage is just extends from base.html

.. code:: python

    {% extends 'gentelella/base.html' %}

Available block are

::

    | - pre_head
    | - head
    |   - meta
    |   - title
    |   - stylesheets
    | - extra_css
    | - extra_head
    | - body
    |   - sidebar
    |   - top_navigation
    |   - content_wrapper
    |     -  messages
    |     -  breadcrumbs
    |     -  content_block_wrap
    |        -  content
    |   - footer
    |   - javascripts
    | - js

You can overwrite all blocks but remember use {{ block.super }}.
Blocks ``extra_css``, ``js`` are designed to be overwrite when you want to include custom
css and js.


Importing javascript libraries
---------------------------------

Django gentelella has a lot of Javascript dependencies, most of them are imported in base.html,
but there are many that you can activate in your template to avoit use import statics files manually.

You can define what library you want using ``define_true`` tag, in this way:

.. code:: html

    {% extends 'gentelella/base.html' %}
    {% load gtsettings %}

    {% block pre_head %}
        {% define_true  "use_datatables" %}
    {% endblock %}

It's very important to implement it in pre_head block, because is the first block processed on base.html,
so it's will run first.

Remember use {% block js %} {% endblock %} to add your custom javascript code.

Available Javascript Libraries
---------------------------------

This list could be grow in the next future.

- use_datatables
- use_chartjs
- use_bootstraptree



Force always include library
----------------------------------

Add in your ``settings.py`` a dictionary called ``DEFAULT_JS_IMPORTS`` with the libs you want to include.

.. code:: python

    DEFAULT_JS_IMPORTS = {
        'use_chartjs': True
    }