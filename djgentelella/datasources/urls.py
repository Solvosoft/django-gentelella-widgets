from django.urls import re_path

from . import api

# Dots are allowed in a name ('ventas.pedidos'); the trailing slash is optional.
NAME = r'^gtapis/datasources/(?P<name>[\w.\-]+)/'

urlpatterns = [
    re_path(NAME + r'$', api.DataSourceInfoView.as_view(), name='gtdatasource'),
    re_path(NAME + r'rows/?$', api.DataSourceRowsView.as_view(),
            name='gtdatasource-rows'),
    re_path(NAME + r'aggregate/?$', api.DataSourceAggregateView.as_view(),
            name='gtdatasource-aggregate'),
    re_path(NAME + r'pivot/?$', api.DataSourcePivotView.as_view(),
            name='gtdatasource-pivot'),
    re_path(NAME + r'facets/?$', api.DataSourceFacetsView.as_view(),
            name='gtdatasource-facets'),
    re_path(NAME + r'export/?$', api.DataSourceExportView.as_view(),
            name='gtdatasource-export'),
]
