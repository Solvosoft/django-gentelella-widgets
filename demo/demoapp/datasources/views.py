from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def datasource_view(request):
    """A table, its facets, smart filter chips and the export menu over the
    ``demoapp.person`` data source (demoapp/gtdatasources.py)."""
    return render(request, 'gentelella/datasources_demo/datasources.html')
