"""What the demo lets design documents use (djgentelella.designs).

Publish the samples with
``python manage.py gtdesigns_publish demoapp/gtdesign/<name>.json`` and open
``/designs/<meta.url>``: ``welcome``, and the catalogue of the components with
data -- ``category_products`` first (``dashboard`` links its rows to it),
then ``products`` and ``dashboard``. ``createdemo`` publishes them all, and
``ticket_kanban``: the help desk flow (``gtflows.py``) as a kanban board at
``/designs/tickets-board/``; ``meetups``: one data source as cards, on a
calendar and on a map (``/designs/meetups/``); ``insights``: a tree, a
timeline and metric cards (``/designs/insights/``); ``shop_orders`` and
``shop_order_done``: an order form whose pipeline checks the stock, computes
the total, takes the stock and goes to another page (``/designs/shop-orders/``).
"""

from django.core.exceptions import ValidationError
from django.db.models import F
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from djgentelella.designs.exposure import expose
from djgentelella.designs.pipeline import process

from demoapp.models import (
    Country, Department, Meetup, Person, Product, ProductCategory, ProductTag,
    ShopItem, ShopOrder, SupportTicket,
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
# The order page of the pipeline (shop_orders.json).
expose(ShopItem)
expose(ShopOrder)


@process('demoapp.check_stock', kind='validation',
         label=gettext_lazy('Check the stock'))
def check_stock(ctx):
    """An order cannot ask for more than the item has in stock."""
    item, quantity = ctx.data.get('item'), ctx.data.get('quantity')
    if item is not None and quantity is not None and quantity > item.stock:
        ctx.add_error('quantity', _('Only %(stock)d of %(item)s in stock.') % {
            'stock': item.stock, 'item': item})


@process('demoapp.order_total', kind='computation',
         label=gettext_lazy('Compute the total'))
def order_total(ctx):
    """``total`` is the quantity times the price of the item."""
    return {'total': ctx.data['item'].price * ctx.data['quantity']}


@process('demoapp.take_stock', kind='process', label=gettext_lazy('Take the stock'))
def take_stock(ctx):
    """Take the quantity from the stock, in the transaction of the save: if
    another order took it first, nothing is saved."""
    order = ctx.instance
    taken = ShopItem.objects.filter(pk=order.item_id,
                                    stock__gte=order.quantity).update(
        stock=F('stock') - order.quantity)
    if not taken:
        raise ValidationError(_('The stock of %(item)s ran out.') % {
            'item': order.item}, code='no_stock')
