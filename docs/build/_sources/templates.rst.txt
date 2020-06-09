Using in templates
====================

Basic usage is just extends from base.html

.. code:: python

    {% extends 'gentelella/base.html' %}

Available block are

::

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

You can overwrite all blocks but remember use {{ block.super }}.