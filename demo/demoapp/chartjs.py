from django.shortcuts import render
from django.urls import reverse


def chart_js_view(request):
    context = {
        'vertical_url': reverse('verticalbar-list'),
        'horizontal_url': reverse('horizontalbar-list'),
        'stacked_url': reverse('stackedbar-list'),
        'line_url': reverse('line-list'),
        'stepped_url': reverse('steppedline-list'),
        'arealine_url': reverse('arealine-list'),
        'pie_url': reverse('pie-list'),
        'doughnut_url': reverse('doughnut-list'),
        'linebar_url': reverse('linebar-list'),
        'scatter_url': reverse('scatter-list'),
    }
    return render(request, 'chartjs.html', context=context)
