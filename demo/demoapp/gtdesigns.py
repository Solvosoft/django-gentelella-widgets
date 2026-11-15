"""What the demo lets design documents use (djgentelella.designs).

Publish the samples with
``python manage.py gtdesigns_publish demoapp/gtdesign/<name>.json`` and open
``/designs/<meta.url>``: ``welcome``, and the catalogue of the components with
data -- ``category_products`` first (``dashboard`` links its rows to it),
then ``products`` and ``dashboard``. ``createdemo`` publishes them all.
"""

from djgentelella.designs.exposure import expose

from demoapp.models import Country, Person, Product, ProductCategory, ProductTag

expose(Country)
expose(Person)
expose(ProductCategory)
expose(ProductTag)
expose(Product)
