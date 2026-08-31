from django.shortcuts import get_object_or_404, render

from ..models import Warehouse


def positionsGridViewExample(request):
    warehouse = get_object_or_404(Warehouse, pk=Warehouse.objects.first().pk)
    return render(
        request,
        'gentelella/positionsgrid/warehouse.html',
        {
            'warehouse': warehouse,
            # Server-rendered seed for the breadcrumbs block: the path is on
            # screen before javascript runs, and BreadcrumbNav takes the same
            # node over afterwards.
            'breadcrumbs': [
                {'label': 'Demo', 'href': '/'},
                {'label': warehouse.name},
            ],
        },
    )
