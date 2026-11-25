"""What the demo lets design documents use (djgentelella.designs).

Publish the samples with
``python manage.py gtdesigns_publish demoapp/gtdesign/<name>.json`` and open
``/designs/<meta.url>``: ``welcome``, and the catalogue of the components with
data -- ``category_products`` first (``dashboard`` links its rows to it),
then ``products`` and ``dashboard``. ``createdemo`` publishes them all, and
``ticket_kanban``: the help desk flow (``gtflows.py``) as a kanban board at
``/designs/tickets-board/``; ``meetups``: one data source as cards, on a
calendar and on a map (``/designs/meetups/``); ``insights``: a tree, a
timeline and metric cards (``/designs/insights/``); ``employee_wizard`` and
``employee_edit``: the ``wizard`` component, hiring an employee in three
steps (``/designs/employees/new/``) and editing one
(``/designs/employees/edit/<pk>``).
"""

from djgentelella.designs.exposure import expose

from demoapp.models import (
    Country, Department, Meetup, NewHire, Person, Product, ProductCategory,
    ProductTag, SupportTicket,
)

expose(Country)
expose(Person)
expose(ProductCategory)
expose(ProductTag)
expose(Product)
# The help desk board (flow_kanban over demoapp.TicketFlow).
expose(SupportTicket)
# The region components (cards, calendar, map) of meetups.json.
expose(Meetup)
# The tree of insights.json.
expose(Department)
# The wizards of employee_wizard.json and employee_edit.json.
expose(NewHire)
