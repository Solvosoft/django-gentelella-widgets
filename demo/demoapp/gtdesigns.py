"""What the demo lets design documents use (djgentelella.designs).

Publish the samples with
``python manage.py gtdesigns_publish demoapp/gtdesign/<name>.json`` and open
``/designs/<meta.url>``: ``welcome``, and the catalogue of the components with
data -- ``category_products`` first (``dashboard`` links its rows to it),
then ``products`` and ``dashboard``. ``createdemo`` publishes them all, and
``ticket_kanban``: the help desk flow (``gtflows.py``) as a kanban board at
``/designs/tickets-board/``; ``meetups``: one data source as cards, on a
calendar and on a map (``/designs/meetups/``).
"""

from djgentelella.designs.exposure import expose

from demoapp.models import (
    Country, Meetup, Person, Product, ProductCategory, ProductTag, SupportTicket,
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
