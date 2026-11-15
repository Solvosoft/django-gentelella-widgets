"""Data sources of the demo, autodiscovered by djgentelella.datasources.

``demoapp.person`` is a plain model source; ``demoapp.purchases`` shows the
argument a ``ModelDataSource`` takes most often, the list of ``fields``,
including one across a relation. The page at ``/datasources/`` uses the first.
"""
from djgentelella.datasources.base import ModelDataSource, register_datasource

from . import models


@register_datasource
class PersonDataSource(ModelDataSource):
    model = models.Person
    name = 'demoapp.person'
    label = 'People'


register_datasource(ModelDataSource(
    models.PurchaseRequest,
    name='demoapp.purchases',
    fields=['id', 'title', 'amount', 'supplier', 'requester',
            'requester__username', 'created_at'],
))
