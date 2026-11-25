"""Data sources of the demo, autodiscovered by djgentelella.datasources.

``demoapp.person`` is a plain model source; ``demoapp.purchases`` shows the
argument a ``ModelDataSource`` takes most often, the list of ``fields``,
including one across a relation. The page at ``/datasources/`` uses the first.

People and countries are also searchable (``@searchable``): the box of the
top bar (``GT_SEARCH_NAVBAR``) and ``/search/`` find them, grouped.
"""
from django.utils.translation import gettext_lazy as _

from djgentelella.datasources.base import ModelDataSource, register_datasource
from djgentelella.search import searchable

from . import models


@register_datasource
@searchable(fields={'name': 'A', 'country__name': 'C'}, title='name',
            subtitle='country__name', url='demoapp_person_detail',
            icon='fa fa-user')
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

register_datasource(searchable(
    fields={'name': 'A', 'code': 'B'}, title='name', subtitle='{code}',
    url='demoapp_country_detail', group=_('Countries'), icon='fa fa-flag',
)(ModelDataSource(models.Country, name='demoapp.country',
                  fields=['id', 'name', 'code'])))

# The meetups of /designs/meetups/ (cards, calendar and map over one source):
# only those of the current Site and the global ones.
register_datasource(ModelDataSource(
    models.Meetup, name='demoapp.meetups', site_field='site',
    fields=['id', 'title', 'kind', 'city', 'starts_at', 'ends_at', 'location',
            'picture'],
))

# The organization chart of /designs/insights/ (tree), by Site like the
# meetups, whose timeline and metric cards are on that page too.
register_datasource(ModelDataSource(
    models.Department, name='demoapp.departments', site_field='site',
    fields=['id', 'name', 'parent', 'icon', 'head'],
))
